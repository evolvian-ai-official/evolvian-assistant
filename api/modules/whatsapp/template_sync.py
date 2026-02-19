import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from api.config.config import supabase

logger = logging.getLogger(__name__)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v22.0")
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
HTTP_TIMEOUT_SECONDS = 18

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


def resolve_waba_id_from_phone(*, wa_phone_id: str, wa_token: str) -> Optional[str]:
    try:
        response = _meta_request(
            "GET",
            f"{wa_phone_id}",
            token=wa_token,
            params={"fields": "whatsapp_business_account"},
        )
        if response.status_code >= 400:
            logger.error("❌ Failed resolving WABA id | %s", _format_meta_error(response))
            return None

        payload = response.json()
        waba = payload.get("whatsapp_business_account") if isinstance(payload, dict) else None
        if isinstance(waba, dict):
            return waba.get("id")
    except Exception:
        logger.exception("❌ resolve_waba_id_from_phone failed")
    return None


def _ensure_body_placeholders(text: str, parameter_count: int) -> str:
    body = (text or "").strip()
    if not body:
        body = "Hola {{1}}, este es un recordatorio de tu cita."

    found = [int(m.group(1)) for m in re.finditer(r"\{\{(\d+)\}\}", body)]
    max_found = max(found) if found else 0

    if parameter_count <= max_found:
        return body

    missing_parts = " ".join(f"{{{{{idx}}}}}" for idx in range(max_found + 1, parameter_count + 1))
    return f"{body} {missing_parts}".strip()


def _build_template_components(*, preview_body: Optional[str], parameter_count: int) -> list[dict]:
    safe_params = max(0, int(parameter_count or 0))
    body_text = _ensure_body_placeholders(preview_body or "", safe_params)

    body_component: dict[str, Any] = {
        "type": "BODY",
        "text": body_text,
    }

    if safe_params > 0:
        body_component["example"] = {
            "body_text": [[f"sample_{idx}" for idx in range(1, safe_params + 1)]]
        }

    return [body_component]


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
    response = (
        supabase
        .table("channels")
        .select("wa_phone_id, wa_token")
        .eq("client_id", client_id)
        .eq("type", "whatsapp")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def _load_canonical_templates() -> list[dict]:
    response = (
        supabase
        .table("meta_approved_templates")
        .select("id, template_name, preview_body, language, parameter_count, type")
        .eq("channel", "whatsapp")
        .eq("is_active", True)
        .order("template_name")
        .execute()
    )
    return response.data or []


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
    try:
        (
            supabase
            .table("client_whatsapp_templates")
            .upsert(row, on_conflict="client_id,meta_template_id")
            .execute()
        )
    except Exception:
        logger.exception(
            "❌ Failed upserting client_whatsapp_templates (is migration applied?) | client_id=%s | meta_template_id=%s",
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

    if existing:
        update_payload = {
            "meta_template_id": meta_template_id,
            "template_name": canonical_template_name,
            "type": template_type,
            "channel": "whatsapp",
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

    frequency = None
    if template_type == "appointment_reminder":
        frequency = [{"offset_minutes": -60, "label": "1 hour before"}]

    insert_payload = {
        "client_id": client_id,
        "channel": "whatsapp",
        "type": template_type,
        "meta_template_id": meta_template_id,
        "template_name": canonical_template_name,
        "label": canonical_template_name,
        "body": None,
        "is_active": bool(preferred_active),
        "frequency": frequency if preferred_active else None,
    }

    try:
        (
            supabase
            .table("message_templates")
            .insert(insert_payload)
            .execute()
        )
    except Exception:
        logger.exception("❌ Failed creating WhatsApp message template binding")


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

    waba_id = resolve_waba_id_from_phone(wa_phone_id=wa_phone_id, wa_token=wa_token)
    if not waba_id:
        result["errors"].append("unable_to_resolve_waba_id")
        return result

    canonical_templates = _load_canonical_templates()
    if not canonical_templates:
        result["success"] = True
        return result

    preferred_meta_by_type: dict[str, str] = {}
    for row in canonical_templates:
        row_type = row.get("type")
        row_id = str(row.get("id") or "")
        if row_type and row_id and row_type not in preferred_meta_by_type:
            preferred_meta_by_type[row_type] = row_id

    existing_remote = _list_meta_templates(waba_id=waba_id, wa_token=wa_token)
    country_code = get_client_country_code(client_id)

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
            created = _create_meta_template(
                waba_id=waba_id,
                wa_token=wa_token,
                template_name=client_template_name,
                language=language,
                category=category,
                components=_build_template_components(
                    preview_body=canonical.get("preview_body"),
                    parameter_count=parameter_count,
                ),
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
                preferred_active=preferred_meta_by_type.get(template_type) == canonical_id_str,
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

    waba_id = resolve_waba_id_from_phone(wa_phone_id=wa_phone_id, wa_token=wa_token)
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
