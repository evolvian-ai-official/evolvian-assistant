import json
import logging
import mimetypes
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from api.config.config import supabase
from api.appointments.template_language_resolution import normalize_language_preferences
from api.security.whatsapp_token_crypto import decrypt_whatsapp_token

logger = logging.getLogger(__name__)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v22.0")
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
HTTP_TIMEOUT_SECONDS = 18
WHATSAPP_TEMPLATE_IMAGE_MAX_BYTES = 5 * 1024 * 1024

_TYPE_TO_CATEGORY = {
    "appointment_reminder": "UTILITY",
    "appointment_confirmation": "UTILITY",
    "appointment_cancellation": "UTILITY",
}

_COUNTRY_ALIASES = {
    "UNITED STATES": "US",
    "USA": "US",
    "US": "US",
    "MEXICO": "MX",
    "MX": "MX",
    "MEX": "MX",
}

_DEFAULT_RATE_CARD_USD: dict[str, dict[str, float]] = {
    "US": {
        "UTILITY": 0.016,
        "MARKETING": 0.026,
        "AUTHENTICATION": 0.014,
        "SERVICE": 0.0,
    },
    "MX": {
        "UTILITY": 0.014,
        "MARKETING": 0.024,
        "AUTHENTICATION": 0.012,
        "SERVICE": 0.0,
    },
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_meta_status(status: Optional[str]) -> str:
    value = (status or "").strip().upper()
    if value in {"APPROVED", "ACTIVE"}:
        return "active"
    if value in {"IN_APPEAL", "PENDING", "PENDING_REVIEW", "IN_REVIEW"}:
        return "pending"
    if value in {"REJECTED", "PAUSED", "DISABLED", "ARCHIVED", "DELETED"}:
        return "inactive"
    return value.lower() if value else "unknown"


def is_status_active(status: Optional[str]) -> bool:
    return _normalize_meta_status(status) == "active"


def infer_template_category(template_type: Optional[str]) -> str:
    if _is_campaign_meta_type(template_type):
        return "MARKETING"
    if not template_type:
        return "UTILITY"
    return _TYPE_TO_CATEGORY.get(template_type.strip().lower(), "UTILITY")


def _sanitize_template_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (value or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "evolvian_template"


def build_client_template_name(canonical_name: str, client_id: str) -> str:
    # Canonical names from meta_approved_templates are the only WhatsApp templates
    # Evolvian should use across accounts. Keep name stable per canonical record.
    _ = client_id  # kept for backwards-compatible signature
    return (canonical_name or "").strip() or _sanitize_template_name(canonical_name)


def _is_campaign_meta_type(template_type: Optional[str]) -> bool:
    probe = str(template_type or "").strip().lower()
    return probe.startswith("campaign_whatsapp")


def _normalize_visibility_scope(row: dict) -> str:
    raw = str((row or {}).get("visibility_scope") or "").strip().lower()
    if raw in {"global", "client_private"}:
        return raw
    return ""


def _normalize_owner_client_id(row: dict) -> Optional[str]:
    value = str((row or {}).get("owner_client_id") or "").strip()
    return value or None


def _is_private_template_row(row: dict) -> bool:
    scope = _normalize_visibility_scope(row)
    if scope == "client_private":
        return True
    if scope == "global":
        return False
    # Legacy fallback before visibility_scope existed.
    return _is_campaign_meta_type((row or {}).get("type"))


def _load_client_owned_campaign_meta_ids(*, client_id: str, candidate_ids: list[str]) -> set[str]:
    ids = [str(value or "").strip() for value in candidate_ids if str(value or "").strip()]
    if not ids:
        return set()
    try:
        try:
            res = (
                supabase
                .table("message_templates")
                .select("meta_template_id,type")
                .eq("client_id", client_id)
                .eq("channel", "whatsapp")
                .eq("variant_key", "campaign")
                .eq("is_active", True)
                .in_("meta_template_id", ids)
                .execute()
            )
        except Exception:
            # Fallback for environments where variant_key is not available yet.
            res = (
                supabase
                .table("message_templates")
                .select("meta_template_id,type")
                .eq("client_id", client_id)
                .eq("channel", "whatsapp")
                .eq("is_active", True)
                .in_("meta_template_id", ids)
                .execute()
            )
        return {
            str((row or {}).get("meta_template_id") or "").strip()
            for row in (res.data or [])
            if str((row or {}).get("meta_template_id") or "").strip()
            and _is_campaign_meta_type((row or {}).get("type"))
        }
    except Exception:
        logger.exception(
            "❌ Failed loading campaign meta ownership map | client_id=%s",
            client_id,
        )
        return set()


def _filter_canonical_templates_for_client(
    templates: list[dict],
    *,
    client_id: str | None,
) -> list[dict]:
    if not templates:
        return []

    visible_rows: list[dict] = []
    unresolved_private_rows: list[dict] = []

    for row in templates:
        template = row or {}
        scope = _normalize_visibility_scope(template)
        owner_client_id = _normalize_owner_client_id(template)

        if scope == "global":
            visible_rows.append(template)
            continue

        if scope == "client_private":
            if client_id and owner_client_id and str(owner_client_id) == str(client_id):
                visible_rows.append(template)
            elif not owner_client_id:
                unresolved_private_rows.append(template)
            continue

        if _is_private_template_row(template):
            unresolved_private_rows.append(template)
        else:
            visible_rows.append(template)

    if not unresolved_private_rows:
        return visible_rows
    if not client_id:
        return visible_rows

    fallback_ids = [str((row or {}).get("id") or "").strip() for row in unresolved_private_rows]
    owned_ids = _load_client_owned_campaign_meta_ids(client_id=client_id, candidate_ids=fallback_ids)
    if not owned_ids:
        return visible_rows

    owned_rows = [
        row for row in unresolved_private_rows
        if str((row or {}).get("id") or "").strip() in owned_ids
    ]
    return [*visible_rows, *owned_rows]


def _format_meta_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict):
            message = str(error.get("message") or response.text)
            code = error.get("code")
            subcode = error.get("error_subcode")
            if code is not None:
                return f"{message} (code={code}, subcode={subcode})"
            return message
    except Exception:
        pass
    return response.text[:500]


def _meta_request(
    method: str,
    path: str,
    *,
    token: str,
    params: Optional[dict] = None,
    json_payload: Optional[dict] = None,
) -> requests.Response:
    url = f"{GRAPH_BASE_URL}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return requests.request(
        method=method.upper(),
        url=url,
        headers=headers,
        params=params,
        json=json_payload,
        timeout=HTTP_TIMEOUT_SECONDS,
    )


def _extract_after_cursor(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    paging = payload.get("paging")
    if not isinstance(paging, dict):
        return None
    cursors = paging.get("cursors")
    if not isinstance(cursors, dict):
        return None
    after = cursors.get("after")
    return str(after) if after else None


def _response_has_unknown_field_error(response: requests.Response) -> bool:
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            return False
        message = str(error.get("message") or "").lower()
        code = error.get("code")
        return bool(code == 100 and "nonexisting field" in message)
    except Exception:
        return False


def _extract_waba_id_from_phone_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    direct = payload.get("waba_id")
    if direct:
        return str(direct)

    legacy = payload.get("whatsapp_business_account")
    if isinstance(legacy, dict) and legacy.get("id"):
        return str(legacy["id"])

    return None


def _list_business_ids_for_token(wa_token: str) -> list[str]:
    business_ids: set[str] = set()

    # Newer Graph setups: /me?fields=businesses{id}
    response = _meta_request(
        "GET",
        "me",
        token=wa_token,
        params={"fields": "businesses{id}"},
    )
    if response.status_code < 400:
        payload = response.json()
        businesses = payload.get("businesses") if isinstance(payload, dict) else None
        data = businesses.get("data") if isinstance(businesses, dict) else []
        for row in data or []:
            business_id = str((row or {}).get("id") or "").strip()
            if business_id:
                business_ids.add(business_id)
    else:
        logger.warning("⚠️ Failed listing businesses from /me | %s", _format_meta_error(response))

    # Legacy/alternative edge: /me/businesses
    after_cursor: Optional[str] = None
    while True:
        params: dict[str, Any] = {"fields": "id", "limit": 200}
        if after_cursor:
            params["after"] = after_cursor

        response = _meta_request(
            "GET",
            "me/businesses",
            token=wa_token,
            params=params,
        )
        if response.status_code >= 400:
            # This edge commonly requires business_management; keep graceful.
            break

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else []
        for row in data or []:
            business_id = str((row or {}).get("id") or "").strip()
            if business_id:
                business_ids.add(business_id)

        after_cursor = _extract_after_cursor(payload)
        if not after_cursor:
            break

    return list(business_ids)


def _list_owned_wabas_for_business(*, business_id: str, wa_token: str) -> list[str]:
    found: list[str] = []
    after_cursor: Optional[str] = None

    while True:
        params: dict[str, Any] = {"fields": "id", "limit": 200}
        if after_cursor:
            params["after"] = after_cursor

        response = _meta_request(
            "GET",
            f"{business_id}/owned_whatsapp_business_accounts",
            token=wa_token,
            params=params,
        )
        if response.status_code >= 400:
            logger.warning(
                "⚠️ Failed listing owned WABAs | business_id=%s | %s",
                business_id,
                _format_meta_error(response),
            )
            break

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else []
        for row in data or []:
            waba_id = str((row or {}).get("id") or "").strip()
            if waba_id:
                found.append(waba_id)

        after_cursor = _extract_after_cursor(payload)
        if not after_cursor:
            break

    return found


def _waba_has_phone_number(*, waba_id: str, wa_phone_id: str, wa_token: str) -> bool:
    after_cursor: Optional[str] = None

    while True:
        params: dict[str, Any] = {"fields": "id", "limit": 200}
        if after_cursor:
            params["after"] = after_cursor

        response = _meta_request(
            "GET",
            f"{waba_id}/phone_numbers",
            token=wa_token,
            params=params,
        )
        if response.status_code >= 400:
            # Some Graph setups return code=100 "nonexisting field (phone_numbers)"
            # for objects that don't expose this edge. Treat it as an unsupported
            # candidate during fallback discovery instead of warning noise.
            if _response_has_unknown_field_error(response):
                logger.debug(
                    "Skipping WABA phone number probe (unsupported edge/object) | waba_id=%s | %s",
                    waba_id,
                    _format_meta_error(response),
                )
                return False
            logger.warning(
                "⚠️ Failed listing phone numbers for WABA | waba_id=%s | %s",
                waba_id,
                _format_meta_error(response),
            )
            return False

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else []
        for row in data or []:
            phone_id = str((row or {}).get("id") or "").strip()
            if phone_id and phone_id == wa_phone_id:
                return True

        after_cursor = _extract_after_cursor(payload)
        if not after_cursor:
            break

    return False


def _resolve_waba_id_via_business_graph(*, wa_phone_id: str, wa_token: str) -> Optional[str]:
    business_ids = _list_business_ids_for_token(wa_token)
    if not business_ids:
        return None

    for business_id in business_ids:
        waba_ids = _list_owned_wabas_for_business(
            business_id=business_id,
            wa_token=wa_token,
        )
        for waba_id in waba_ids:
            if _waba_has_phone_number(
                waba_id=waba_id,
                wa_phone_id=wa_phone_id,
                wa_token=wa_token,
            ):
                return waba_id

    return None


def resolve_waba_id_from_phone(*, wa_phone_id: str, wa_token: str) -> Optional[str]:
    try:
        normalized_phone_id = str(wa_phone_id or "").strip()
        if not normalized_phone_id:
            return None

        # Try direct phone-node fields first. Some Graph versions expose only one.
        for field_name in ("waba_id", "whatsapp_business_account"):
            response = _meta_request(
                "GET",
                normalized_phone_id,
                token=wa_token,
                params={"fields": field_name},
            )
            if response.status_code >= 400:
                if _response_has_unknown_field_error(response):
                    continue
                logger.warning(
                    "⚠️ Direct WABA lookup failed | phone_id=%s | field=%s | %s",
                    normalized_phone_id,
                    field_name,
                    _format_meta_error(response),
                )
                continue

            direct_id = _extract_waba_id_from_phone_payload(response.json())
            if direct_id:
                return direct_id

        # Robust fallback: discover businesses -> owned WABAs -> phone_numbers.
        fallback = _resolve_waba_id_via_business_graph(
            wa_phone_id=normalized_phone_id,
            wa_token=wa_token,
        )
        if fallback:
            return fallback

        # Optional env fallback for single-WABA environments.
        env_waba = str(os.getenv("WHATSAPP_WABA_ID") or "").strip()
        if env_waba and _waba_has_phone_number(
            waba_id=env_waba,
            wa_phone_id=normalized_phone_id,
            wa_token=wa_token,
        ):
            logger.warning("⚠️ Using WHATSAPP_WABA_ID fallback for phone_id=%s", normalized_phone_id)
            return env_waba

        logger.error("❌ Failed resolving WABA id | phone_id=%s", normalized_phone_id)
    except Exception:
        logger.exception("❌ resolve_waba_id_from_phone failed")
    return None


def validate_waba_access(*, waba_id: str, wa_token: str) -> bool:
    normalized_waba_id = str(waba_id or "").strip()
    if not normalized_waba_id:
        return False
    try:
        response = _meta_request(
            "GET",
            normalized_waba_id,
            token=wa_token,
            params={"fields": "id"},
        )
        if response.status_code >= 400:
            logger.warning(
                "⚠️ WABA access validation failed | waba_id=%s | %s",
                normalized_waba_id,
                _format_meta_error(response),
            )
            return False

        payload = response.json()
        remote_id = str((payload or {}).get("id") or "").strip()
        return remote_id == normalized_waba_id
    except Exception:
        logger.exception("❌ validate_waba_access failed | waba_id=%s", normalized_waba_id)
        return False


def validate_waba_phone_binding(
    *,
    waba_id: str,
    wa_phone_id: str,
    wa_token: str,
) -> bool:
    normalized_waba_id = str(waba_id or "").strip()
    normalized_phone_id = str(wa_phone_id or "").strip()
    if not normalized_waba_id or not normalized_phone_id:
        return False
    if not validate_waba_access(waba_id=normalized_waba_id, wa_token=wa_token):
        return False
    return _waba_has_phone_number(
        waba_id=normalized_waba_id,
        wa_phone_id=normalized_phone_id,
        wa_token=wa_token,
    )


def _ensure_body_placeholders(text: str, parameter_count: int) -> str:
    body = (text or "").strip()
    if not body:
        body = "Hola {{1}}, este es un recordatorio de tu cita."

    # Normalize legacy placeholders like "{1}" into Meta-compatible "{{1}}".
    body = re.sub(r"(?<!\{)\{(\d+)\}(?!\})", r"{{\1}}", body)

    found = [int(m.group(1)) for m in re.finditer(r"\{\{(\d+)\}\}", body)]
    max_found = max(found) if found else 0

    if parameter_count <= max_found:
        return body

    missing_parts = " ".join(f"{{{{{idx}}}}}" for idx in range(max_found + 1, parameter_count + 1))
    return f"{body} {missing_parts}".strip()


def _default_quick_reply_button_specs(*, template_type: Optional[str], language: Optional[str]) -> list[dict]:
    normalized_type = str(template_type or "").strip().lower()
    if normalized_type not in {"appointment_confirmation", "appointment_reminder"}:
        return []

    family, _ = normalize_language_preferences(locale_code=language)
    text = "Cancel" if family == "en" else "Cancelar"
    return [{"type": "QUICK_REPLY", "text": text}]


def _normalize_template_button_url(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = f"https://{raw.lstrip('/')}"
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return candidate[:2000]


def _normalize_template_buttons(
    *,
    buttons_json: Any,
    template_type: Optional[str],
    language: Optional[str],
) -> list[dict]:
    raw = buttons_json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    if isinstance(raw, dict):
        raw = raw.get("buttons")

    if not isinstance(raw, list):
        raw = _default_quick_reply_button_specs(
            template_type=template_type,
            language=language,
        )

    normalized: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        button_type = str(item.get("type") or "").strip().upper()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if button_type == "QUICK_REPLY":
            normalized.append({"type": "QUICK_REPLY", "text": text[:25]})
        elif button_type == "URL":
            url = _normalize_template_button_url(item.get("url"))
            if not url:
                continue
            normalized.append({"type": "URL", "text": text[:25], "url": url})
        else:
            continue
        if len(normalized) >= 10:
            break

    return normalized


def _normalize_template_header_image_url(
    *,
    buttons_json: Any,
    header_image_url: Optional[str] = None,
) -> Optional[str]:
    def _looks_like_media_handle(value: str) -> bool:
        probe = str(value or "").strip()
        if not probe:
            return False
        if probe.startswith("https://") or probe.startswith("http://"):
            return False
        if " " in probe:
            return False
        return ":" in probe

    direct = str(header_image_url or "").strip()
    if _looks_like_media_handle(direct):
        return direct[:2000]

    raw = buttons_json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    if not isinstance(raw, dict):
        return None

    header = raw.get("header")
    if not isinstance(header, dict):
        return None

    header_type = str(header.get("type") or "").strip().upper()
    if header_type and header_type != "IMAGE":
        return None

    candidate = str(
        header.get("image_url")
        or header.get("url")
        or header.get("link")
        or ""
    ).strip()
    if _looks_like_media_handle(candidate):
        return candidate[:2000]
    return None


def _extract_template_header_image_url(
    *,
    buttons_json: Any,
    header_image_url: Optional[str] = None,
) -> Optional[str]:
    direct = str(header_image_url or "").strip()
    if direct.startswith("https://") or direct.startswith("http://"):
        return direct[:2000]

    raw = buttons_json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    if not isinstance(raw, dict):
        return None

    header = raw.get("header")
    if not isinstance(header, dict):
        return None

    candidate = str(
        header.get("image_url")
        or header.get("url")
        or header.get("link")
        or ""
    ).strip()
    if candidate.startswith("https://") or candidate.startswith("http://"):
        return candidate[:2000]
    return None


def _download_template_header_image(image_url: str) -> tuple[bytes, str, str]:
    response = requests.get(
        image_url,
        timeout=HTTP_TIMEOUT_SECONDS,
        stream=True,
        headers={"User-Agent": "Evolvian-TemplateSync/1.0"},
    )
    response.raise_for_status()

    parsed = urlparse(image_url)
    file_name = os.path.basename(parsed.path or "") or "template_image.jpg"
    content_type = str(response.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not content_type:
        guessed, _ = mimetypes.guess_type(file_name)
        content_type = str(guessed or "").strip().lower()
    if content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        # Normalize jpg alias and reject unsupported mime upfront.
        if content_type == "image/pjpeg":
            content_type = "image/jpeg"
        elif content_type in {"image/webp", "image/gif"}:
            raise ValueError(f"unsupported_image_type:{content_type}")
        elif not content_type:
            content_type = "image/jpeg"

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > WHATSAPP_TEMPLATE_IMAGE_MAX_BYTES:
            raise ValueError("image_too_large_for_template_header")
        chunks.append(chunk)

    binary = b"".join(chunks)
    if not binary:
        raise ValueError("empty_image_payload")

    if content_type == "image/jpg":
        content_type = "image/jpeg"

    if "." not in file_name:
        ext = ".png" if content_type == "image/png" else ".jpg"
        file_name = f"{file_name}{ext}"

    return binary, content_type, file_name


def _create_resumable_upload_session_id(
    *,
    owner_id: str,
    wa_token: str,
    file_name: str,
    file_length: int,
    file_type: str,
) -> Optional[str]:
    response = _meta_request(
        "POST",
        f"{owner_id}/uploads",
        token=wa_token,
        params={
            "file_name": file_name,
            "file_length": str(file_length),
            "file_type": file_type,
        },
    )
    if response.status_code >= 400:
        return None
    try:
        payload = response.json() if response.text else {}
    except Exception:
        payload = {}
    session_id = str((payload or {}).get("id") or (payload or {}).get("upload_id") or "").strip()
    return session_id or None


def _upload_binary_to_resumable_session(
    *,
    session_id: str,
    wa_token: str,
    binary: bytes,
) -> Optional[str]:
    url = f"{GRAPH_BASE_URL}/{str(session_id or '').lstrip('/')}"
    auth_headers = [
        {"Authorization": f"OAuth {wa_token}"},
        {"Authorization": f"Bearer {wa_token}"},
    ]
    for auth in auth_headers:
        try:
            response = requests.post(
                url,
                headers={
                    **auth,
                    "file_offset": "0",
                    "Content-Type": "application/octet-stream",
                },
                data=binary,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except Exception:
            continue
        if response.status_code >= 400:
            continue
        try:
            payload = response.json() if response.text else {}
        except Exception:
            payload = {}
        handle = str((payload or {}).get("h") or (payload or {}).get("handle") or "").strip()
        if handle:
            return handle[:2000]
    return None


def _generate_template_header_handle(
    *,
    image_url: str,
    wa_token: str,
    waba_id: str,
) -> Optional[str]:
    try:
        binary, mime_type, file_name = _download_template_header_image(image_url)
    except Exception:
        logger.warning("⚠️ Failed downloading template header image | url=%s", image_url)
        return None

    owner_candidates = [
        str(waba_id or "").strip(),
        str(os.getenv("WHATSAPP_BUSINESS_ID") or "").strip(),
        str(os.getenv("META_APP_ID") or "").strip(),
        str(os.getenv("WHATSAPP_APP_ID") or "").strip(),
    ]
    owner_candidates = [value for value in owner_candidates if value]

    for owner_id in owner_candidates:
        session_id = _create_resumable_upload_session_id(
            owner_id=owner_id,
            wa_token=wa_token,
            file_name=file_name,
            file_length=len(binary),
            file_type=mime_type,
        )
        if not session_id:
            continue
        handle = _upload_binary_to_resumable_session(
            session_id=session_id,
            wa_token=wa_token,
            binary=binary,
        )
        if handle:
            return handle
    return None


def _is_meta_invalid_parameter_error(error_text: Any) -> bool:
    probe = str(error_text or "").lower()
    if not probe:
        return False
    return (
        "invalid parameter" in probe
        or "code=100" in probe
        or "subcode=2388299" in probe
    )


def _build_template_components(
    *,
    preview_body: Optional[str],
    parameter_count: int,
    template_type: Optional[str] = None,
    language: Optional[str] = None,
    buttons_json: Any = None,
    header_image_url: Optional[str] = None,
) -> list[dict]:
    safe_params = max(0, int(parameter_count or 0))
    if _is_campaign_meta_type(template_type):
        # Normalize all marketing campaign templates to single variable payload.
        # Keep variable away from terminal position to satisfy Meta validation.
        safe_params = 1
        family, _ = normalize_language_preferences(locale_code=language)
        body_seed = (
            "Hello,\n\n{{1}}\n\nThank you."
            if family == "en"
            else "Hola,\n\n{{1}}\n\nGracias."
        )
        body_text = _ensure_body_placeholders(body_seed, safe_params)
    else:
        body_text = _ensure_body_placeholders(preview_body or "", safe_params)

    body_component: dict[str, Any] = {
        "type": "BODY",
        "text": body_text,
    }

    if safe_params > 0:
        body_component["example"] = {
            "body_text": [[f"sample_{idx}" for idx in range(1, safe_params + 1)]]
        }

    components: list[dict] = []

    normalized_header_image_url = _normalize_template_header_image_url(
        buttons_json=buttons_json,
        header_image_url=header_image_url,
    )
    if normalized_header_image_url:
        components.append(
            {
                "type": "HEADER",
                "format": "IMAGE",
                "example": {"header_handle": [normalized_header_image_url]},
            }
        )

    components.append(body_component)

    buttons = _normalize_template_buttons(
        buttons_json=buttons_json,
        template_type=template_type,
        language=language,
    )
    if buttons:
        components.append({
            "type": "BUTTONS",
            "buttons": buttons,
        })

    return components


def _load_rate_card() -> dict[str, dict[str, float]]:
    raw = os.getenv("META_TEMPLATE_RATE_CARD_USD_JSON", "").strip()
    if not raw:
        return _DEFAULT_RATE_CARD_USD

    try:
        decoded = json.loads(raw)
        if isinstance(decoded, dict):
            normalized: dict[str, dict[str, float]] = {}
            for country, category_map in decoded.items():
                if not isinstance(category_map, dict):
                    continue
                normalized[str(country).upper()] = {
                    str(category).upper(): float(value)
                    for category, value in category_map.items()
                    if isinstance(value, (int, float))
                }
            if normalized:
                return normalized
    except Exception:
        logger.exception("⚠️ Invalid META_TEMPLATE_RATE_CARD_USD_JSON; using defaults")

    return _DEFAULT_RATE_CARD_USD


def estimate_template_pricing(
    *,
    category: Optional[str],
    country_code: Optional[str],
) -> dict:
    normalized_category = (category or "UTILITY").strip().upper() or "UTILITY"
    normalized_country = (country_code or "US").strip().upper() or "US"

    rate_card = _load_rate_card()
    country_rates = rate_card.get(normalized_country) or rate_card.get("US", {})

    if normalized_category == "SERVICE":
        amount = 0.0
    else:
        amount = float(country_rates.get(normalized_category, 0.0))

    return {
        "category": normalized_category,
        "country_code": normalized_country,
        "currency": "USD",
        "unit_cost_estimate": amount,
        "billable": amount > 0,
        "pricing_source": "evolvian_estimate_v1",
        "pricing_disclaimer": (
            "Estimated cost. Final charges are defined by Meta rate card and conversation context."
        ),
    }


def get_client_country_code(client_id: str) -> str:
    try:
        response = (
            supabase
            .table("client_profile")
            .select("country")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            country = (rows[0].get("country") or "").strip().upper()
            if country:
                if country in _COUNTRY_ALIASES:
                    return _COUNTRY_ALIASES[country]
                if len(country) == 2 and country.isalpha():
                    return country
    except Exception:
        logger.exception("⚠️ Failed loading client country for pricing | client_id=%s", client_id)
    return "US"


def get_active_whatsapp_channel(client_id: str) -> Optional[dict]:
    try:
        response = (
            supabase
            .table("channels")
            .select("id, wa_phone_id, wa_token, wa_business_account_id")
            .eq("client_id", client_id)
            .eq("type", "whatsapp")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
    except Exception:
        # Backward-compatible fallback when only wa_waba_id exists.
        try:
            response = (
                supabase
                .table("channels")
                .select("id, wa_phone_id, wa_token, wa_waba_id")
                .eq("client_id", client_id)
                .eq("type", "whatsapp")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
        except Exception:
            response = (
                supabase
                .table("channels")
                .select("id, wa_phone_id, wa_token")
                .eq("client_id", client_id)
                .eq("type", "whatsapp")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )

    rows = response.data or []
    if not rows:
        return None

    row = dict(rows[0] or {})
    if not row.get("wa_business_account_id") and row.get("wa_waba_id"):
        row["wa_business_account_id"] = row.get("wa_waba_id")
    row.setdefault("wa_business_account_id", None)
    row["wa_token"] = decrypt_whatsapp_token(row.get("wa_token"))

    return row


def _persist_channel_waba_id(
    *,
    client_id: str,
    channel_id: Optional[str],
    waba_id: str,
) -> None:
    if not waba_id:
        return

    update_payload = {
        "wa_business_account_id": waba_id,
        "updated_at": _utcnow_iso(),
    }

    try:
        query = (
            supabase
            .table("channels")
            .update(update_payload)
        )

        if channel_id:
            query = query.eq("id", channel_id)
        else:
            query = (
                query
                .eq("client_id", client_id)
                .eq("type", "whatsapp")
                .eq("is_active", True)
            )

        query.execute()

    except Exception:
        logger.warning(
            "⚠️ Unable to persist wa_business_account_id cache (migration may be pending)"
        )



def _resolve_channel_waba_id(*, client_id: str, channel: dict) -> Optional[str]:
    cached = str(channel.get("wa_business_account_id") or "").strip()

    if cached:
        return cached

    wa_phone_id = str(channel.get("wa_phone_id") or "").strip()
    wa_token = str(channel.get("wa_token") or "").strip()
    if not wa_phone_id or not wa_token:
        return None

    resolved = resolve_waba_id_from_phone(wa_phone_id=wa_phone_id, wa_token=wa_token)
    if not resolved:
        return None

    _persist_channel_waba_id(
        client_id=client_id,
        channel_id=str(channel.get("id") or "").strip() or None,
        waba_id=resolved,
    )
    return resolved


def _load_canonical_templates(*, client_id: str | None = None) -> list[dict]:
    attempts: list[tuple[str, bool]] = [
        (
            "id, template_name, preview_body, language, parameter_count, type, "
            "buttons_json, header_example_media_url, owner_client_id, visibility_scope",
            True,
        ),
        (
            "id, template_name, preview_body, language, parameter_count, type, "
            "buttons_json, header_example_media_url, owner_client_id, visibility_scope",
            False,
        ),
        (
            "id, template_name, preview_body, language, parameter_count, type, "
            "buttons_json, owner_client_id, visibility_scope",
            True,
        ),
        (
            "id, template_name, preview_body, language, parameter_count, type, "
            "buttons_json, owner_client_id, visibility_scope",
            False,
        ),
        (
            "id, template_name, preview_body, language, parameter_count, type, "
            "owner_client_id, visibility_scope",
            False,
        ),
        ("id, template_name, preview_body, language, parameter_count, type, buttons_json", True),
        ("id, template_name, preview_body, language, parameter_count, type, buttons_json", False),
        ("id, template_name, preview_body, language, parameter_count, type", False),
    ]

    last_error: Exception | None = None
    for select_fields, with_provision_enabled in attempts:
        try:
            query = (
                supabase
                .table("meta_approved_templates")
                .select(select_fields)
                .eq("channel", "whatsapp")
                .eq("is_active", True)
            )
            if with_provision_enabled:
                query = query.eq("provision_enabled", True)
            rows = query.order("template_name").execute().data or []
            return _filter_canonical_templates_for_client(rows, client_id=client_id)
        except Exception as exc:
            last_error = exc
            continue

    logger.warning(
        "⚠️ Failed loading canonical Meta templates after compatibility fallbacks | error=%s",
        last_error,
    )
    return []


def _list_meta_templates(*, waba_id: str, wa_token: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    after_cursor: Optional[str] = None

    while True:
        params = {
            "fields": "id,name,status,language,category",
            "limit": 200,
        }
        if after_cursor:
            params["after"] = after_cursor

        response = _meta_request(
            "GET",
            f"{waba_id}/message_templates",
            token=wa_token,
            params=params,
        )
        if response.status_code >= 400:
            logger.error("❌ Failed listing Meta templates | %s", _format_meta_error(response))
            break

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list):
            for item in data:
                name = str(item.get("name") or "").strip().lower()
                if name:
                    found[name] = item

        paging = payload.get("paging", {}) if isinstance(payload, dict) else {}
        cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}
        after_cursor = cursors.get("after")
        if not after_cursor:
            break

    return found


def _create_meta_template(
    *,
    waba_id: str,
    wa_token: str,
    template_name: str,
    language: str,
    category: str,
    components: list[dict],
) -> dict:
    payload = {
        "name": template_name,
        "language": language,
        "category": category,
        "components": components,
    }

    response = _meta_request(
        "POST",
        f"{waba_id}/message_templates",
        token=wa_token,
        json_payload=payload,
    )

    if response.status_code < 400:
        parsed = response.json() if response.text else {}
        return {
            "success": True,
            "already_exists": False,
            "status": "pending",
            "remote_id": parsed.get("id") if isinstance(parsed, dict) else None,
            "error": None,
        }

    error_text = _format_meta_error(response)
    lower_error = error_text.lower()
    if "already exists" in lower_error or "duplicate" in lower_error:
        return {
            "success": True,
            "already_exists": True,
            "status": "pending",
            "remote_id": None,
            "error": None,
        }

    return {
        "success": False,
        "already_exists": False,
        "status": "inactive",
        "remote_id": None,
        "error": error_text,
    }


def _upsert_client_template_record(row: dict) -> None:
    client_id = str(row.get("client_id") or "").strip()
    meta_template_id = str(row.get("meta_template_id") or "").strip()
    meta_template_name = str(row.get("meta_template_name") or "").strip()

    def _update_by_id(record_id: str, payload: dict) -> bool:
        if not record_id:
            return False
        try:
            updated = (
                supabase
                .table("client_whatsapp_templates")
                .update(payload)
                .eq("id", record_id)
                .execute()
            )
            return bool(updated.data or [])
        except Exception:
            return False

    def _find_one_by_meta_id() -> dict | None:
        if not client_id or not meta_template_id:
            return None
        try:
            res = (
                supabase
                .table("client_whatsapp_templates")
                .select("id,meta_template_id,meta_template_name")
                .eq("client_id", client_id)
                .eq("meta_template_id", meta_template_id)
                .limit(1)
                .execute()
            )
            return (res.data or [None])[0]
        except Exception:
            return None

    def _find_one_by_meta_name() -> dict | None:
        if not client_id or not meta_template_name:
            return None
        try:
            res = (
                supabase
                .table("client_whatsapp_templates")
                .select("id,meta_template_id,meta_template_name")
                .eq("client_id", client_id)
                .eq("meta_template_name", meta_template_name)
                .limit(1)
                .execute()
            )
            return (res.data or [None])[0]
        except Exception:
            return None

    try:
        (
            supabase
            .table("client_whatsapp_templates")
            .upsert(row, on_conflict="client_id,meta_template_id")
            .execute()
        )
        return
    except Exception as upsert_error:
        logger.warning(
            "⚠️ Upsert client_whatsapp_templates failed; falling back to update/insert "
            "(likely missing unique index on client_id,meta_template_id) | "
            "client_id=%s | meta_template_id=%s | error=%s",
            row.get("client_id"),
            row.get("meta_template_id"),
            upsert_error,
        )

    # Reconcile existing rows in environments with legacy duplicate collisions.
    by_meta = _find_one_by_meta_id()
    by_name = _find_one_by_meta_name()

    if by_meta and by_name and str(by_meta.get("id")) != str(by_name.get("id")):
        duplicate_id = str(by_name.get("id") or "").strip()
        # Prefer record keyed by meta_template_id as source of truth.
        if duplicate_id:
            try:
                (
                    supabase
                    .table("client_whatsapp_templates")
                    .delete()
                    .eq("id", duplicate_id)
                    .execute()
                )
            except Exception:
                logger.warning(
                    "⚠️ Could not delete duplicate client_whatsapp_templates row | client_id=%s | duplicate_id=%s",
                    client_id,
                    duplicate_id,
                )
        # Refresh pointers after possible cleanup.
        by_meta = _find_one_by_meta_id() or by_meta
        by_name = _find_one_by_meta_name()

    if by_meta:
        payload = dict(row)
        if by_name and str(by_name.get("id") or "").strip() != str(by_meta.get("id") or "").strip():
            # Keep stable name to avoid unique collision if another row still holds requested name.
            payload.pop("meta_template_name", None)
        if _update_by_id(str(by_meta.get("id") or "").strip(), payload):
            return

    if by_name:
        if _update_by_id(str(by_name.get("id") or "").strip(), row):
            return

    # Fallback path for environments where constraints/indexes were not applied.
    try:
        updated = (
            supabase
            .table("client_whatsapp_templates")
            .update(row)
            .eq("client_id", client_id)
            .eq("meta_template_id", meta_template_id)
            .execute()
        )
        if (updated.data or []):
            return
    except Exception:
        logger.exception(
            "⚠️ Fallback update failed for client_whatsapp_templates | client_id=%s | meta_template_id=%s",
            row.get("client_id"),
            row.get("meta_template_id"),
        )

    try:
        (
            supabase
            .table("client_whatsapp_templates")
            .insert(row)
            .execute()
        )
    except Exception:
        logger.exception(
            "❌ Fallback insert failed for client_whatsapp_templates | client_id=%s | meta_template_id=%s",
            row.get("client_id"),
            row.get("meta_template_id"),
        )


def _find_existing_whatsapp_message_template(
    *,
    client_id: str,
    meta_template_id: str,
    canonical_template_name: str,
    template_type: Optional[str],
) -> Optional[dict]:
    try:
        by_meta = (
            supabase
            .table("message_templates")
            .select("id, meta_template_id, is_active, frequency")
            .eq("client_id", client_id)
            .eq("channel", "whatsapp")
            .eq("meta_template_id", meta_template_id)
            .limit(1)
            .execute()
        )
        rows = by_meta.data or []
        if rows:
            return rows[0]
    except Exception:
        logger.exception("❌ Failed querying message_templates by meta_template_id")

    if not template_type:
        return None

    try:
        by_name = (
            supabase
            .table("message_templates")
            .select("id, meta_template_id, is_active, frequency")
            .eq("client_id", client_id)
            .eq("channel", "whatsapp")
            .eq("type", template_type)
            .eq("template_name", canonical_template_name)
            .limit(1)
            .execute()
        )
        rows = by_name.data or []
        if rows:
            return rows[0]
    except Exception:
        logger.exception("❌ Failed querying message_templates by template_name")

    return None


def _ensure_whatsapp_template_binding(
    *,
    client_id: str,
    meta_template_id: str,
    canonical_template_name: str,
    template_type: Optional[str],
    language: Optional[str],
    meta_status_active: bool,
    preferred_active: bool,
) -> None:
    if not template_type:
        return

    existing = _find_existing_whatsapp_message_template(
        client_id=client_id,
        meta_template_id=meta_template_id,
        canonical_template_name=canonical_template_name,
        template_type=template_type,
    )

    frequency = None
    if template_type == "appointment_reminder":
        frequency = [{"offset_minutes": -60, "label": "1 hour before"}]

    if existing:
        language_family, locale_code = normalize_language_preferences(locale_code=language)
        existing_frequency = existing.get("frequency")
        update_payload = {
            "meta_template_id": meta_template_id,
            "template_name": canonical_template_name,
            "type": template_type,
            "channel": "whatsapp",
            "language_family": language_family,
            "locale_code": locale_code,
            "variant_key": "default",
            "priority": 100 if preferred_active else 0,
            "is_default_for_language": bool(preferred_active and meta_status_active),
            # Keep local binding aligned with language-specific preferred template selection.
            "is_active": bool(meta_status_active),
            "frequency": (
                existing_frequency
                if template_type == "appointment_reminder" and existing_frequency
                else (frequency if preferred_active else None)
            ),
            "updated_at": _utcnow_iso(),
        }
        try:
            (
                supabase
                .table("message_templates")
                .update(update_payload)
                .eq("id", existing["id"])
                .execute()
            )
        except Exception:
            logger.exception("❌ Failed updating existing WhatsApp message template binding")
        return

    language_family, locale_code = normalize_language_preferences(locale_code=language)

    insert_payload = {
        "client_id": client_id,
        "channel": "whatsapp",
        "type": template_type,
        "meta_template_id": meta_template_id,
        "template_name": canonical_template_name,
        "label": canonical_template_name,
        "language_family": language_family,
        "locale_code": locale_code,
        "variant_key": "default",
        "priority": 100 if preferred_active else 0,
        "is_default_for_language": bool(preferred_active and meta_status_active),
        "body": None,
        "is_active": bool(meta_status_active),
        "frequency": frequency if preferred_active else None,
    }

    try:
        (
            supabase
            .table("message_templates")
            .insert(insert_payload)
            .execute()
        )
        return
    except Exception:
        logger.exception("❌ Failed creating WhatsApp message template binding")

    # Fallback for legacy schemas/rows where a uniqueness constraint blocks inserts.
    # Reuse an existing slot for same client+type+language and bind it to the canonical template.
    try:
        reusable_candidates = (
            supabase
            .table("message_templates")
            .select("id, meta_template_id, language_family, locale_code, frequency, is_active")
            .eq("client_id", client_id)
            .eq("channel", "whatsapp")
            .eq("type", template_type)
            .limit(20)
            .execute()
        )
        rows = reusable_candidates.data or []
        target_family, target_locale = normalize_language_preferences(locale_code=language)

        def _row_score(row: dict) -> tuple[int, int, int]:
            row_meta = bool(row.get("meta_template_id"))
            row_family = str(row.get("language_family") or "").strip().lower()
            row_locale = str(row.get("locale_code") or "").strip().lower()
            same_family = row_family == target_family
            same_locale = row_locale == str(target_locale or "").lower()
            # Prefer rows without canonical binding, then same locale/family.
            return (
                0 if not row_meta else 1,
                0 if same_locale else (1 if same_family else 2),
                0 if row.get("is_active") else 1,
            )

        if rows:
            rows = sorted(rows, key=_row_score)
            candidate = rows[0]
            existing_frequency = candidate.get("frequency")
            update_payload = {
                "meta_template_id": meta_template_id,
                "template_name": canonical_template_name,
                "label": canonical_template_name,
                "channel": "whatsapp",
                "type": template_type,
                "language_family": target_family,
                "locale_code": target_locale,
                "variant_key": "default",
                "priority": 100 if preferred_active else 0,
                "is_default_for_language": bool(preferred_active and meta_status_active),
                "is_active": bool(meta_status_active),
                "frequency": (
                    existing_frequency
                    if template_type == "appointment_reminder" and existing_frequency
                    else (frequency if preferred_active else None)
                ),
                "updated_at": _utcnow_iso(),
            }
            (
                supabase
                .table("message_templates")
                .update(update_payload)
                .eq("id", candidate["id"])
                .execute()
            )
    except Exception:
        logger.exception(
            "❌ Fallback reuse failed for WhatsApp message template binding | client_id=%s | type=%s | language=%s",
            client_id,
            template_type,
            language,
        )


def _reconcile_whatsapp_message_bindings_from_sync_rows(*, client_id: str) -> None:
    """
    Ensure local message_templates bindings stay aligned with client_whatsapp_templates statuses.
    This is used after refresh_status so "Meta ready" and "Appointments ready" don't drift.
    """
    try:
        rows_res = (
            supabase
            .table("client_whatsapp_templates")
            .select("meta_template_id, canonical_template_name, template_type, language, status, is_active")
            .eq("client_id", client_id)
            .execute()
        )
    except Exception:
        logger.exception("❌ Failed loading client_whatsapp_templates for binding reconciliation | client_id=%s", client_id)
        return

    rows = rows_res.data or []
    if not rows:
        return

    preferred_meta_by_type_language: dict[tuple[str, str], str] = {}
    for row in _load_canonical_templates(client_id=client_id):
        row_type = str(row.get("type") or "")
        row_id = str(row.get("id") or "")
        if not row_type or not row_id:
            continue
        row_family, _ = normalize_language_preferences(locale_code=row.get("language"))
        preferred_meta_by_type_language.setdefault((row_type, row_family), row_id)

    for row in rows:
        meta_template_id = str(row.get("meta_template_id") or "")
        template_type = row.get("template_type")
        language = row.get("language")
        if not meta_template_id or not template_type:
            continue

        row_family, _ = normalize_language_preferences(locale_code=language)
        preferred_active = (
            preferred_meta_by_type_language.get((str(template_type or ""), row_family))
            == meta_template_id
        )
        meta_status_active = bool(row.get("is_active")) and is_status_active(row.get("status"))

        _ensure_whatsapp_template_binding(
            client_id=client_id,
            meta_template_id=meta_template_id,
            canonical_template_name=str(row.get("canonical_template_name") or ""),
            template_type=template_type,
            language=language,
            meta_status_active=meta_status_active,
            preferred_active=preferred_active,
        )


def sync_canonical_templates_for_client(
    *,
    client_id: str,
    force_refresh: bool = False,
) -> dict:
    result = {
        "success": False,
        "client_id": client_id,
        "synced": 0,
        "active": 0,
        "inactive": 0,
        "pending": 0,
        "errors": [],
    }

    channel = get_active_whatsapp_channel(client_id)
    if not channel:
        result["errors"].append("whatsapp_channel_not_configured")
        return result

    wa_phone_id = channel.get("wa_phone_id")
    wa_token = channel.get("wa_token")
    if not wa_phone_id or not wa_token:
        result["errors"].append("whatsapp_channel_credentials_missing")
        return result

    waba_id = _resolve_channel_waba_id(client_id=client_id, channel=channel)
    if not waba_id:
        result["errors"].append("unable_to_resolve_waba_id")
        return result

    canonical_templates = _load_canonical_templates(client_id=client_id)
    if not canonical_templates:
        result["success"] = True
        return result

    preferred_meta_by_type_language: dict[tuple[str, str], str] = {}
    for row in canonical_templates:
        row_type = row.get("type")
        row_id = str(row.get("id") or "")
        row_family, _ = normalize_language_preferences(locale_code=row.get("language"))
        key = (str(row_type or ""), row_family)
        if row_type and row_id and key not in preferred_meta_by_type_language:
            preferred_meta_by_type_language[key] = row_id

    existing_remote = _list_meta_templates(waba_id=waba_id, wa_token=wa_token)
    country_code = get_client_country_code(client_id)
    header_handle_cache: dict[str, Optional[str]] = {}

    for canonical in canonical_templates:
        canonical_id = canonical.get("id")
        canonical_name = canonical.get("template_name") or "template"
        language = (canonical.get("language") or "es_MX").strip() or "es_MX"
        parameter_count = int(canonical.get("parameter_count") or 0)
        template_type = canonical.get("type")
        category = infer_template_category(template_type)
        client_template_name = build_client_template_name(canonical_name, client_id)

        remote = existing_remote.get(client_template_name.lower())
        status = None
        remote_id = None
        error_reason = None

        if remote and not force_refresh:
            status = _normalize_meta_status(remote.get("status"))
            remote_id = remote.get("id")
        else:
            resolved_header_handle = _normalize_template_header_image_url(
                buttons_json=canonical.get("buttons_json"),
                header_image_url=canonical.get("header_example_media_url"),
            )
            if not resolved_header_handle:
                header_image_url = _extract_template_header_image_url(
                    buttons_json=canonical.get("buttons_json"),
                    header_image_url=canonical.get("header_example_media_url"),
                )
                if header_image_url:
                    cache_key = f"{client_id}:{header_image_url}"
                    if cache_key in header_handle_cache:
                        resolved_header_handle = header_handle_cache.get(cache_key)
                    else:
                        resolved_header_handle = _generate_template_header_handle(
                            image_url=header_image_url,
                            wa_token=wa_token,
                            waba_id=waba_id,
                        )
                        header_handle_cache[cache_key] = resolved_header_handle

            components = _build_template_components(
                preview_body=canonical.get("preview_body"),
                parameter_count=parameter_count,
                template_type=template_type,
                language=language,
                buttons_json=canonical.get("buttons_json"),
                header_image_url=resolved_header_handle,
            )
            created = _create_meta_template(
                waba_id=waba_id,
                wa_token=wa_token,
                template_name=client_template_name,
                language=language,
                category=category,
                components=components,
            )
            if (
                not created["success"]
                and _is_meta_invalid_parameter_error(created.get("error"))
                and any(
                    str((component or {}).get("type") or "").upper() == "HEADER"
                    and str((component or {}).get("format") or "").upper() == "IMAGE"
                    for component in components
                )
            ):
                fallback_components = [
                    component
                    for component in components
                    if not (
                        str((component or {}).get("type") or "").upper() == "HEADER"
                        and str((component or {}).get("format") or "").upper() == "IMAGE"
                    )
                ]
                if fallback_components != components:
                    created = _create_meta_template(
                        waba_id=waba_id,
                        wa_token=wa_token,
                        template_name=client_template_name,
                        language=language,
                        category=category,
                        components=fallback_components,
                    )
            if (
                not created["success"]
                and _is_meta_invalid_parameter_error(created.get("error"))
            ):
                # Last-resort compatibility fallback:
                # some accounts reject certain button/header combinations.
                # Retry with BODY-only components to keep sync healthy.
                body_only_components = [
                    component
                    for component in components
                    if str((component or {}).get("type") or "").upper() == "BODY"
                ]
                if body_only_components:
                    created = _create_meta_template(
                        waba_id=waba_id,
                        wa_token=wa_token,
                        template_name=client_template_name,
                        language=language,
                        category=category,
                        components=body_only_components,
                    )

            if not created["success"]:
                status = "inactive"
                error_reason = created.get("error")
                result["errors"].append(
                    f"{canonical_name}: {created.get('error') or 'create_failed'}"
                )
            else:
                status = created.get("status") or "pending"
                remote_id = created.get("remote_id")

        pricing = estimate_template_pricing(
            category=category,
            country_code=country_code,
        )

        row = {
            "client_id": client_id,
            "meta_template_id": canonical_id,
            "canonical_template_name": canonical_name,
            "meta_template_name": client_template_name,
            "template_type": template_type,
            "category": category,
            "language": language,
            "status": status,
            "is_active": status == "active",
            "meta_template_remote_id": remote_id,
            "status_reason": error_reason,
            "pricing_currency": pricing["currency"],
            "estimated_unit_cost": pricing["unit_cost_estimate"],
            "billable": pricing["billable"],
            "pricing_source": pricing["pricing_source"],
            "updated_at": _utcnow_iso(),
            "last_synced_at": _utcnow_iso(),
        }
        _upsert_client_template_record(row)

        canonical_id_str = str(canonical_id or "")
        if canonical_id_str:
            _ensure_whatsapp_template_binding(
                client_id=client_id,
                meta_template_id=canonical_id_str,
                canonical_template_name=canonical_name,
                template_type=template_type,
                language=language,
                meta_status_active=(status == "active"),
                preferred_active=(
                    preferred_meta_by_type_language.get(
                        (str(template_type or ""), normalize_language_preferences(locale_code=language)[0])
                    )
                    == canonical_id_str
                ),
            )

        result["synced"] += 1
        if status == "active":
            result["active"] += 1
        elif status == "inactive":
            result["inactive"] += 1
        else:
            result["pending"] += 1

    if result["synced"] > 0:
        refreshed = refresh_client_template_statuses(client_id=client_id)
        result["active"] = refreshed.get("active", result["active"])
        result["inactive"] = refreshed.get("inactive", result["inactive"])
        result["pending"] = refreshed.get("pending", result["pending"])

    result["success"] = len(result["errors"]) == 0
    return result


def refresh_client_template_statuses(*, client_id: str) -> dict:
    outcome = {
        "success": False,
        "client_id": client_id,
        "checked": 0,
        "active": 0,
        "inactive": 0,
        "pending": 0,
        "errors": [],
    }

    channel = get_active_whatsapp_channel(client_id)
    if not channel:
        outcome["errors"].append("whatsapp_channel_not_configured")
        return outcome

    wa_phone_id = channel.get("wa_phone_id")
    wa_token = channel.get("wa_token")
    if not wa_phone_id or not wa_token:
        outcome["errors"].append("whatsapp_channel_credentials_missing")
        return outcome

    waba_id = _resolve_channel_waba_id(client_id=client_id, channel=channel)
    if not waba_id:
        outcome["errors"].append("unable_to_resolve_waba_id")
        return outcome

    try:
        local_res = (
            supabase
            .table("client_whatsapp_templates")
            .select("id, meta_template_name")
            .eq("client_id", client_id)
            .execute()
        )
    except Exception:
        logger.exception("❌ Failed querying client_whatsapp_templates for status refresh")
        outcome["errors"].append("client_template_table_unavailable")
        return outcome

    local_rows = local_res.data or []
    if not local_rows:
        outcome["success"] = True
        return outcome

    remote_map = _list_meta_templates(waba_id=waba_id, wa_token=wa_token)
    now_iso = _utcnow_iso()

    for row in local_rows:
        local_name = str(row.get("meta_template_name") or "").strip().lower()
        remote = remote_map.get(local_name)
        status = _normalize_meta_status(remote.get("status") if remote else "inactive")
        remote_id = remote.get("id") if remote else None

        try:
            (
                supabase
                .table("client_whatsapp_templates")
                .update(
                    {
                        "status": status,
                        "is_active": status == "active",
                        "meta_template_remote_id": remote_id,
                        "updated_at": now_iso,
                        "last_synced_at": now_iso,
                    }
                )
                .eq("id", row["id"])
                .execute()
            )
        except Exception:
            logger.exception("❌ Failed updating template status row | id=%s", row.get("id"))
            outcome["errors"].append(f"update_failed:{row.get('id')}")

        outcome["checked"] += 1
        if status == "active":
            outcome["active"] += 1
        elif status == "inactive":
            outcome["inactive"] += 1
        else:
            outcome["pending"] += 1

    try:
        _reconcile_whatsapp_message_bindings_from_sync_rows(client_id=client_id)
    except Exception:
        logger.exception(
            "❌ Failed post-refresh WhatsApp message_templates reconciliation | client_id=%s",
            client_id,
        )
        outcome["errors"].append("message_template_binding_reconcile_failed")

    outcome["success"] = len(outcome["errors"]) == 0
    return outcome


def get_client_template_sync_map(client_id: str) -> dict[str, dict]:
    try:
        response = (
            supabase
            .table("client_whatsapp_templates")
            .select(
                "meta_template_id,meta_template_name,status,is_active,category,pricing_currency,"
                "estimated_unit_cost,billable,pricing_source,status_reason,last_synced_at"
            )
            .eq("client_id", client_id)
            .execute()
        )
    except Exception:
        logger.warning("⚠️ Failed loading client template map (migration pending?)")
        return {}

    mapped: dict[str, dict] = {}
    for row in response.data or []:
        key = str(row.get("meta_template_id") or "")
        if key:
            mapped[key] = row
    return mapped
