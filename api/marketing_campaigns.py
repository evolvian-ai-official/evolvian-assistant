from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Literal, Optional
from urllib.parse import quote_plus, urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.authz import authorize_client_request
from api.compliance.email_marketing_standard import (
    CAMPAIGN_OWNER_TOKEN,
    POSTAL_ADDRESS_TOKEN,
    UNSUBSCRIBE_TOKEN,
)
from api.config.config import supabase
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_template_for_client
from api.modules.assistant_rag.llm import openai_chat
from api.privacy_dsr import split_details_and_metadata
from api.utils.feature_access import get_client_plan_id
from api.compliance.marketing_consent_adapter import backfill_default_marketing_consents_for_contacts
from api.security.unsubscribe_client_id_crypto import encrypt_unsubscribe_client_id

router = APIRouter(prefix="/marketing", tags=["Marketing Campaigns"])

PLAN_ORDER = {"free": 0, "starter": 1, "premium": 2, "white_label": 3, "enterprise": 3}
SEGMENT_ORDER = {"clients": 0, "leads": 1}
ALLOWED_SEGMENTS = {"clients", "leads"}
TERMINAL_OPT_OUT_STATUSES = {"withdrawn", "denied"}
WHATSAPP_OPT_OUT_KEYWORDS = (
    "stop",
    "unsubscribe",
    "optout",
    "opt out",
    "desuscribir",
    "desuscribirme",
    "darme de baja",
    "no recibir",
    "no mas",
    "no más",
)
_MEXICO_COUNTRY_ALIASES = {"mx", "mex", "mexico", "méxico"}


class CampaignCreatePayload(BaseModel):
    client_id: str
    name: str = Field(..., min_length=3, max_length=120)
    channel: Literal["email", "whatsapp"]
    subject: Optional[str] = Field(None, max_length=180)
    body: str = Field(..., min_length=3, max_length=6000)
    image_url: Optional[str] = Field(None, max_length=900)
    cta_mode: Optional[Literal["url"]] = None
    cta_label: Optional[str] = Field(None, max_length=80)
    cta_url: Optional[str] = Field(None, max_length=900)
    language_family: Optional[Literal["es", "en"]] = "es"
    status: Optional[Literal["draft", "scheduled", "active"]] = "draft"
    whatsapp_interest_enabled: Optional[bool] = True
    whatsapp_interest_label: Optional[str] = Field(None, max_length=25)
    whatsapp_opt_out_enabled: Optional[bool] = True
    whatsapp_opt_out_label: Optional[str] = Field(None, max_length=25)


class CampaignUpdatePayload(BaseModel):
    client_id: str
    name: Optional[str] = Field(None, min_length=3, max_length=120)
    subject: Optional[str] = Field(None, max_length=180)
    body: Optional[str] = Field(None, min_length=3, max_length=6000)
    image_url: Optional[str] = Field(None, max_length=900)
    cta_mode: Optional[Literal["url"]] = None
    cta_label: Optional[str] = Field(None, max_length=80)
    cta_url: Optional[str] = Field(None, max_length=900)
    language_family: Optional[Literal["es", "en"]] = None
    status: Optional[Literal["draft", "scheduled", "active", "paused", "sent", "archived"]] = None
    whatsapp_interest_enabled: Optional[bool] = None
    whatsapp_interest_label: Optional[str] = Field(None, max_length=25)
    whatsapp_opt_out_enabled: Optional[bool] = None
    whatsapp_opt_out_label: Optional[str] = Field(None, max_length=25)


class CampaignSendPayload(BaseModel):
    client_id: str
    recipient_keys: Optional[list[str]] = None
    segment_filters: Optional[list[Literal["clients", "leads"]]] = None
    limit: int = Field(200, ge=1, le=1000)
    dry_run: bool = False
    unsubscribe_base_url: Optional[str] = None


class CampaignRewritePayload(BaseModel):
    client_id: str
    body: str = Field(..., min_length=3, max_length=6000)
    channel: Literal["email", "whatsapp"] = "email"
    language_family: Optional[Literal["es", "en"]] = "es"
    cta_mode: Optional[Literal["url"]] = None
    cta_label: Optional[str] = Field(None, max_length=80)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


@lru_cache(maxsize=512)
def _get_client_country_code(client_id: str) -> str:
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return ""
    try:
        rows = (
            supabase
            .table("client_profile")
            .select("country")
            .eq("client_id", normalized_client_id)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            raw_country = str((rows[0] or {}).get("country") or "").strip().lower()
            if raw_country in _MEXICO_COUNTRY_ALIASES:
                return "MX"
            if len(raw_country) == 2 and raw_country.isalpha():
                return raw_country.upper()
    except Exception:
        pass
    return ""


def _normalize_phone(value: Any, *, client_id: Optional[str] = None) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if not cleaned:
        return None
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None

    client_country = _get_client_country_code(str(client_id or "").strip()) if client_id else ""
    if len(digits) == 10 and client_country == "MX":
        digits = f"52{digits}"

    # Normalize legacy MX format 521XXXXXXXXXX -> 52XXXXXXXXXX
    if digits.startswith("521") and len(digits) == 13:
        digits = "52" + digits[3:]
    if len(digits) == 10:
        return None

    # Basic E.164 sanity checks.
    if len(digits) < 10 or len(digits) > 15:
        return None
    # Mexico numbers in E.164 should be country code 52 + 10 digits.
    if digits.startswith("52") and len(digits) != 12:
        return None

    return f"+{digits}"


def _normalize_name(value: Any) -> Optional[str]:
    cleaned = " ".join(str(value or "").strip().split())
    return cleaned or None


def _normalize_redirect_url(value: Any) -> Optional[str]:
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
    return candidate[:900]


def _recipient_key(email: Optional[str], phone: Optional[str], name: Optional[str], *, prefix: str = "contact") -> Optional[str]:
    if email:
        return f"email:{email}"
    if phone:
        return f"phone:{phone}"
    if name:
        slug = re.sub(r"\s+", "_", name.strip().lower())
        slug = re.sub(r"[^a-z0-9_]+", "", slug)
        if slug:
            return f"{prefix}:name:{slug}"
    return None


def _segment_label(segment: str) -> tuple[str, str]:
    if segment == "clients":
        return ("Clients", "Clientes")
    return ("Leads", "Leads")


def _ensure_premium_access(client_id: str) -> None:
    plan_id = str(get_client_plan_id(client_id) or "free").strip().lower()
    current = PLAN_ORDER.get(plan_id, 0)
    required = PLAN_ORDER["premium"]
    if current < required:
        raise HTTPException(
            status_code=403,
            detail=f"Marketing campaigns require premium plan (current plan: {plan_id}).",
        )


def _ensure_whatsapp_channel_connected(client_id: str) -> None:
    rows = (
        supabase.table("channels")
        .select("id,provider,wa_phone_id,wa_token,is_active,active")
        .eq("client_id", client_id)
        .eq("type", "whatsapp")
        .execute()
    ).data or []

    for row in rows:
        is_active = row.get("is_active")
        if is_active is None:
            is_active = row.get("active")
        if is_active is False:
            continue
        if str(row.get("wa_phone_id") or "").strip() and str(row.get("wa_token") or "").strip():
            return

    raise HTTPException(
        status_code=409,
        detail="WhatsApp is not connected. Connect WhatsApp before sending WhatsApp campaigns.",
    )


def _is_missing_marketing_tables(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = [
        "marketing_campaigns",
        "marketing_campaign_recipients",
        "marketing_campaign_events",
    ]
    return any(marker in msg for marker in markers) and (
        "does not exist" in msg or "relation" in msg or "schema cache" in msg or "not found" in msg
    )


def _ensure_template_type_exists(template_type: str, description: str) -> None:
    existing = (
        supabase.table("template_types")
        .select("id")
        .eq("id", template_type)
        .limit(1)
        .execute()
    )
    if existing.data:
        return
    supabase.table("template_types").insert({"id": template_type, "description": description}).execute()


def _format_locale(language_family: Optional[str]) -> str:
    return "en_US" if str(language_family or "").lower().startswith("en") else "es_MX"


def _rewrite_campaign_body(payload: CampaignRewritePayload) -> str:
    lang = "English" if str(payload.language_family or "").lower().startswith("en") else "Spanish"
    channel = str(payload.channel or "email").lower()
    cta_mode = str(payload.cta_mode or "none").lower()
    cta_label = str(payload.cta_label or "").strip()

    system = (
        "You are a senior conversion copywriter for SMB outbound campaigns. "
        "Rewrite provided campaign text to be clearer, concise, persuasive, and compliant. "
        "Do not invent discounts, prices, legal claims, or guarantees. "
        f"Return ONLY the rewritten body text in {lang}."
    )
    user = (
        f"Channel: {channel}\n"
        f"Language: {lang}\n"
        f"CTA mode: {cta_mode}\n"
        f"CTA label: {cta_label or '(not provided)'}\n\n"
        "Requirements:\n"
        "- Keep original intent.\n"
        "- Improve structure and readability.\n"
        "- Include one clear CTA sentence at the end.\n"
        "- If channel=whatsapp, keep it compact (3-5 short lines).\n\n"
        f"Original text:\n{payload.body}"
    )

    rewritten = openai_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        model="gpt-4o-mini",
        timeout=15,
    )
    text = str(rewritten or "").strip()
    if not text or text.lower().startswith("error:"):
        return str(payload.body or "").strip()
    return text[:6000]


def _build_email_template_body(
    *,
    body_text: str,
    image_url: Optional[str],
    cta_mode: Optional[str],
    cta_label: Optional[str],
    cta_url: Optional[str],
) -> str:
    safe_body = str(body_text or "").strip().replace("\n", "<br />\n")
    parts = [f"<div>{safe_body}</div>"]
    normalized_cta_url = _normalize_redirect_url(cta_url)

    if image_url:
        parts.append(
            "<div style='margin-top:16px;'>"
            f"<img src='{image_url}' alt='campaign' style='max-width:100%;height:auto;border-radius:10px;' />"
            "</div>"
        )

    if normalized_cta_url:
        button_label = (cta_label or "Open").strip() or "Open"
        parts.append(
            "<div style='margin-top:18px;'>"
            f"<a href='{normalized_cta_url}' "
            "style='display:inline-block;padding:10px 16px;border-radius:8px;background:#1f6feb;color:#ffffff;text-decoration:none;'>"
            f"{button_label}</a></div>"
        )

    # Required tokens for marketing compliance pipeline.
    parts.append(
        "<div style='display:none;'>"
        f"{UNSUBSCRIBE_TOKEN} {CAMPAIGN_OWNER_TOKEN} {POSTAL_ADDRESS_TOKEN}"
        "</div>"
    )

    return "\n".join(parts)


def _generate_meta_template_name(campaign_name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", str(campaign_name or "campaign").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_") or "campaign"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"mk_{slug}_{stamp}"


def _default_whatsapp_opt_out_label(language_family: Optional[str]) -> str:
    return "Stop updates" if str(language_family or "").lower().startswith("en") else "No recibir más"


def _default_whatsapp_interest_label(language_family: Optional[str]) -> str:
    return "I'm interested" if str(language_family or "").lower().startswith("en") else "Me interesa"


def _normalize_whatsapp_interest_label(value: Any, language_family: Optional[str]) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        text = _default_whatsapp_interest_label(language_family)
    return text[:25]


def _normalize_whatsapp_opt_out_label(value: Any, language_family: Optional[str]) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        text = _default_whatsapp_opt_out_label(language_family)
    return text[:25]


def _decode_buttons_json(value: Any) -> dict[str, Any]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, list):
        return {"buttons": raw}
    return raw if isinstance(raw, dict) else {}


def _extract_campaign_whatsapp_controls(
    *,
    buttons_json: Any,
    language_family: Optional[str],
) -> dict[str, Any]:
    decoded = _decode_buttons_json(buttons_json)
    buttons = decoded.get("buttons")
    opt_out_label = None
    interest_label = None
    has_url_button = False
    has_explicit_button_purpose = False
    quick_reply_labels: list[str] = []
    if isinstance(buttons, list):
        for item in buttons:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().upper()
            if item_type == "URL":
                has_url_button = True
                continue
            if item_type != "QUICK_REPLY":
                continue
            candidate = " ".join(str(item.get("text") or "").strip().split())
            if not candidate:
                continue
            candidate = candidate[:25]
            quick_reply_labels.append(candidate)
            purpose = str(item.get("purpose") or "").strip().lower()
            if purpose:
                has_explicit_button_purpose = True
            if purpose == "interest" and not interest_label:
                interest_label = candidate
                continue
            if purpose == "opt_out" and not opt_out_label:
                opt_out_label = candidate
                continue
        if not opt_out_label:
            for candidate in quick_reply_labels:
                normalized = candidate.lower().strip()
                if any(keyword in normalized for keyword in WHATSAPP_OPT_OUT_KEYWORDS):
                    opt_out_label = candidate
                    break
        if not opt_out_label and len(quick_reply_labels) == 1 and not has_explicit_button_purpose:
            # Legacy templates used one quick reply and it represented opt-out.
            opt_out_label = quick_reply_labels[0]
        if not interest_label:
            for candidate in quick_reply_labels:
                if opt_out_label and candidate == opt_out_label:
                    continue
                normalized = candidate.lower().strip()
                if any(keyword in normalized for keyword in WHATSAPP_OPT_OUT_KEYWORDS):
                    continue
                interest_label = candidate
                break
    header = decoded.get("header")
    has_image_header = (
        isinstance(header, dict)
        and str(header.get("type") or "").strip().upper() == "IMAGE"
        and bool(str(header.get("image_url") or header.get("url") or header.get("link") or "").strip())
    )
    return {
        "whatsapp_interest_enabled": bool(interest_label),
        "whatsapp_interest_label": interest_label or _default_whatsapp_interest_label(language_family),
        "whatsapp_opt_out_enabled": bool(opt_out_label),
        "whatsapp_opt_out_label": opt_out_label or _default_whatsapp_opt_out_label(language_family),
        "whatsapp_has_image_header": bool(has_image_header),
        "whatsapp_has_url_button": bool(has_url_button),
    }


def _load_meta_template_buttons(meta_template_id: Any) -> Optional[Any]:
    normalized_meta_id = str(meta_template_id or "").strip()
    if not normalized_meta_id:
        return None
    try:
        res = (
            supabase.table("meta_approved_templates")
            .select("buttons_json")
            .eq("id", normalized_meta_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        return row.get("buttons_json")
    except Exception:
        return None


def _disable_meta_template_header(meta_template_id: Any) -> bool:
    normalized_meta_id = str(meta_template_id or "").strip()
    if not normalized_meta_id:
        return False
    raw_buttons = _load_meta_template_buttons(normalized_meta_id)
    if raw_buttons is None:
        return False
    decoded = _decode_buttons_json(raw_buttons)
    if not decoded:
        return False
    if not isinstance(decoded.get("header"), dict):
        return False
    decoded.pop("header", None)
    try:
        (
            supabase.table("meta_approved_templates")
            .update(
                {
                    "buttons_json": decoded or None,
                    "updated_at": _now_iso(),
                }
            )
            .eq("id", normalized_meta_id)
            .execute()
        )
        return True
    except Exception:
        return False


def _disable_meta_template_url_buttons(meta_template_id: Any) -> bool:
    normalized_meta_id = str(meta_template_id or "").strip()
    if not normalized_meta_id:
        return False
    raw_buttons = _load_meta_template_buttons(normalized_meta_id)
    if raw_buttons is None:
        return False
    decoded = _decode_buttons_json(raw_buttons)
    if not decoded:
        return False

    buttons = decoded.get("buttons")
    if not isinstance(buttons, list):
        return False

    filtered = [
        item
        for item in buttons
        if not (
            isinstance(item, dict)
            and str(item.get("type") or "").strip().upper() == "URL"
        )
    ]
    if len(filtered) == len(buttons):
        return False

    decoded["buttons"] = filtered
    if not decoded["buttons"]:
        decoded.pop("buttons", None)

    try:
        (
            supabase.table("meta_approved_templates")
            .update(
                {
                    "buttons_json": decoded or None,
                    "updated_at": _now_iso(),
                }
            )
            .eq("id", normalized_meta_id)
            .execute()
        )
        return True
    except Exception:
        return False


def _is_meta_template_parameter_error(error_text: Any) -> bool:
    probe = str(error_text or "").strip().lower()
    if not probe:
        return False
    return (
        "(#132018)" in probe
        or "code=132018" in probe
        or "issue with the parameters in your template" in probe
        or "invalid parameter" in probe
    )


def _enrich_campaign_for_ui(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row or {})
    channel = str(enriched.get("channel") or "").strip().lower()
    if channel != "whatsapp":
        enriched["whatsapp_interest_enabled"] = False
        enriched["whatsapp_interest_label"] = _default_whatsapp_interest_label(enriched.get("language_family"))
        enriched["whatsapp_opt_out_enabled"] = False
        enriched["whatsapp_opt_out_label"] = _default_whatsapp_opt_out_label(enriched.get("language_family"))
        enriched["whatsapp_has_image_header"] = bool(str(enriched.get("image_url") or "").strip())
        enriched["whatsapp_has_url_button"] = bool(_normalize_redirect_url(enriched.get("cta_url")))
        return enriched

    raw_buttons = _load_meta_template_buttons(enriched.get("meta_template_id"))
    if raw_buttons is None:
        controls = {
            "whatsapp_interest_enabled": True,
            "whatsapp_interest_label": _default_whatsapp_interest_label(enriched.get("language_family")),
            "whatsapp_opt_out_enabled": False,
            "whatsapp_opt_out_label": _default_whatsapp_opt_out_label(enriched.get("language_family")),
            # Backward-compatible fallback: preserve previous image-send behavior.
            "whatsapp_has_image_header": bool(str(enriched.get("image_url") or "").strip()),
            "whatsapp_has_url_button": bool(_normalize_redirect_url(enriched.get("cta_url"))),
        }
    else:
        controls = _extract_campaign_whatsapp_controls(
            buttons_json=raw_buttons,
            language_family=enriched.get("language_family"),
        )
    enriched.update(controls)
    return enriched


def _campaign_template_type(base: str) -> str:
    # Keep one template row per campaign snapshot without hitting
    # unique constraints on (client_id, channel, type).
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{base}_{suffix}"


def _create_email_template_for_campaign(client_id: str, payload: CampaignCreatePayload) -> dict[str, Any]:
    template_type = _campaign_template_type("campaign_email")
    _ensure_template_type_exists(template_type, "Marketing campaign email snapshot")

    rendered = _build_email_template_body(
        body_text=payload.body,
        image_url=payload.image_url,
        cta_mode=payload.cta_mode,
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
    )

    data = {
        "client_id": client_id,
        "channel": "email",
        "type": template_type,
        "label": payload.name,
        "body": rendered,
        "is_active": True,
        "language_family": payload.language_family or "es",
        "locale_code": _format_locale(payload.language_family),
        "variant_key": "campaign",
        "priority": 0,
        "is_default_for_language": False,
    }
    result = supabase.table("message_templates").insert(data).execute()
    row = (result.data or [None])[0]
    if not row:
        raise HTTPException(status_code=500, detail="Could not create email campaign template")
    return row


def _campaign_interest_tracking_base_url() -> str:
    api_base = (
        os.getenv("EVOLVIAN_API_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://evolvianai.com"
    ).strip().rstrip("/")
    return f"{api_base}/api/public/marketing/interest/click"


def _build_campaign_interest_tracking_url(
    *,
    campaign_id: str,
    channel: str,
    recipient_key: Optional[str] = None,
    recipient_key_placeholder: Optional[str] = None,
) -> str:
    base = _campaign_interest_tracking_base_url()
    campaign_q = quote_plus(str(campaign_id or "").strip())
    channel_q = quote_plus(str(channel or "").strip().lower() or "unknown")
    if recipient_key_placeholder is not None:
        # Keep placeholder literal for Meta template variable expansion.
        return f"{base}?campaign_id={campaign_q}&channel={channel_q}&recipient_key={recipient_key_placeholder}"
    recipient_q = quote_plus(str(recipient_key or "").strip())
    return f"{base}?campaign_id={campaign_q}&channel={channel_q}&recipient_key={recipient_q}"


def _create_whatsapp_template_for_campaign(
    client_id: str,
    payload: CampaignCreatePayload,
    *,
    campaign_id: str,
) -> dict[str, Any]:
    template_type = _campaign_template_type("campaign_whatsapp")
    _ensure_template_type_exists(template_type, "Marketing campaign WhatsApp snapshot")

    locale_code = _format_locale(payload.language_family)
    # Keep campaign templates stable for Meta approval:
    # all campaign content is sent as single variable {{1}}.
    # Keep variable away from final position to satisfy Meta validation rules.
    preview_body = (
        "Hello,\n\n{{1}}\n\nThank you."
        if str(payload.language_family or "").lower().startswith("en")
        else "Hola,\n\n{{1}}\n\nGracias."
    )

    meta_template_name = _generate_meta_template_name(payload.name)
    normalized_cta_url = _normalize_redirect_url(payload.cta_url) or ""
    normalized_cta_label = str(payload.cta_label or "").strip()
    normalized_image_url = str(payload.image_url or "").strip()
    normalized_interest_enabled = bool(
        True if payload.whatsapp_interest_enabled is None else payload.whatsapp_interest_enabled
    )
    normalized_interest_label = _normalize_whatsapp_interest_label(
        payload.whatsapp_interest_label,
        payload.language_family,
    )
    normalized_opt_out_enabled = bool(
        True if payload.whatsapp_opt_out_enabled is None else payload.whatsapp_opt_out_enabled
    )
    normalized_opt_out_label = _normalize_whatsapp_opt_out_label(
        payload.whatsapp_opt_out_label,
        payload.language_family,
    )
    if normalized_cta_url and not normalized_cta_label:
        normalized_cta_label = "Open site" if str(payload.language_family or "").lower().startswith("en") else "Abrir sitio"

    buttons_payload: dict[str, Any] = {}
    normalized_buttons: list[dict[str, Any]] = []
    if normalized_cta_url:
        tracking_url_with_placeholder = _build_campaign_interest_tracking_url(
            campaign_id=campaign_id,
            channel="whatsapp",
            recipient_key_placeholder="{{1}}",
        )
        normalized_buttons.append(
            {
                "type": "URL",
                "text": normalized_cta_label[:25] or "Open",
                "url": tracking_url_with_placeholder[:2000],
                "purpose": "redirect",
            }
        )
    if normalized_interest_enabled:
        normalized_buttons.append(
            {
                "type": "QUICK_REPLY",
                "text": normalized_interest_label,
                "purpose": "interest",
            }
        )
    if normalized_opt_out_enabled:
        normalized_buttons.append(
            {
                "type": "QUICK_REPLY",
                "text": normalized_opt_out_label,
                "purpose": "opt_out",
            }
        )
    if normalized_buttons:
        buttons_payload["buttons"] = normalized_buttons[:10]
    if normalized_image_url and (normalized_image_url.startswith("https://") or normalized_image_url.startswith("http://")):
        buttons_payload["header"] = {
            "type": "IMAGE",
            "image_url": normalized_image_url[:2000],
        }

    buttons_json = buttons_payload or None

    meta_insert = {
        "template_name": meta_template_name,
        "channel": "whatsapp",
        "parameter_count": 1,
        "preview_body": preview_body,
        "language": locale_code,
        "is_active": True,
        "type": template_type,
        "provision_enabled": True,
        "owner_client_id": client_id,
        "visibility_scope": "client_private",
        "buttons_json": buttons_json,
    }

    try:
        meta_res = supabase.table("meta_approved_templates").insert(meta_insert).execute()
    except Exception:
        # Backward-compatible fallback before newer optional columns are migrated.
        legacy_insert = dict(meta_insert)
        legacy_insert.pop("owner_client_id", None)
        legacy_insert.pop("visibility_scope", None)
        try:
            meta_res = supabase.table("meta_approved_templates").insert(legacy_insert).execute()
        except Exception:
            legacy_insert.pop("buttons_json", None)
            legacy_insert.pop("provision_enabled", None)
            meta_res = supabase.table("meta_approved_templates").insert(legacy_insert).execute()
    meta_row = (meta_res.data or [None])[0]
    if not meta_row:
        raise HTTPException(status_code=500, detail="Could not create Meta template record")

    message_template_insert = {
        "client_id": client_id,
        "channel": "whatsapp",
        "type": template_type,
        "meta_template_id": meta_row.get("id"),
        "template_name": meta_template_name,
        "label": payload.name,
        "is_active": True,
        "language_family": payload.language_family or "es",
        "locale_code": locale_code,
        "variant_key": "campaign",
        "priority": 0,
        "is_default_for_language": False,
    }
    message_res = supabase.table("message_templates").insert(message_template_insert).execute()
    message_row = (message_res.data or [None])[0]
    if not message_row:
        raise HTTPException(status_code=500, detail="Could not create WhatsApp campaign template")

    return {
        "meta": meta_row,
        "message_template": message_row,
        "meta_template_name": meta_template_name,
        "locale_code": locale_code,
    }


def _as_epoch(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _extract_opt_out_scope_client_id(details: Any) -> Optional[str]:
    try:
        plain_details, metadata = split_details_and_metadata(str(details or ""))
        scoped = str((metadata or {}).get("client_id") or "").strip()
        if scoped:
            return scoped
        # Backward compatibility for earlier plain-text format:
        # "... client_id=<uuid>"
        match = re.search(r"\bclient_id=([a-f0-9-]{8,})\b", plain_details, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip()
    except Exception:
        return None
    return None


def _load_opted_out_emails_for_client(client_id: str, candidate_emails: list[str]) -> set[str]:
    normalized_candidates = sorted({str(_normalize_email(e) or "") for e in candidate_emails if _normalize_email(e)})
    if not normalized_candidates:
        return set()

    opted_out: set[str] = set()
    chunk_size = 120

    for start in range(0, len(normalized_candidates), chunk_size):
        chunk = normalized_candidates[start : start + chunk_size]
        try:
            rows = (
                supabase.table("public_privacy_requests")
                .select("email,status,created_at,details")
                .eq("request_type", "marketing_opt_out")
                .in_("email", chunk)
                .order("created_at", desc=True)
                .limit(5000)
                .execute()
            ).data or []
        except Exception:
            rows = []

        rows_by_email: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            email = _normalize_email((row or {}).get("email"))
            if not email:
                continue
            bucket = rows_by_email.get(email)
            if not bucket:
                bucket = []
                rows_by_email[email] = bucket
            bucket.append(row or {})

        for email, email_rows in rows_by_email.items():
            # Evaluate the most recent row that applies to this client scope.
            latest_applicable: Optional[dict[str, Any]] = None
            for row in email_rows:
                scoped_client_id = _extract_opt_out_scope_client_id((row or {}).get("details"))
                if scoped_client_id and str(scoped_client_id) != str(client_id):
                    continue
                latest_applicable = row or {}
                break

            if not latest_applicable:
                continue

            status = str((latest_applicable or {}).get("status") or "pending").strip().lower()
            if status in TERMINAL_OPT_OUT_STATUSES:
                continue
            opted_out.add(email)

    return opted_out


def _load_marketing_consent_renewal_days(client_id: str) -> int:
    try:
        row = (
            supabase.table("client_settings")
            .select("consent_renewal_days")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        ).data or [{}]
        value = int((row[0] or {}).get("consent_renewal_days") or 90)
    except Exception:
        value = 90
    return max(1, min(value, 3650))


def _resolve_marketing_policy_reason(
    *,
    channel: str,
    email: Optional[str],
    phone: Optional[str],
    is_opted_out: bool,
    consent_at: Optional[str],
    consent_terms_accepted: bool,
    consent_email_marketing_accepted: bool,
    consent_email_present: bool,
    consent_phone_present: bool,
    consent_renewal_days: int,
    now_epoch: float,
) -> Optional[str]:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel == "email" and not email:
        return "missing_recipient_email"
    if normalized_channel == "whatsapp" and not phone:
        return "missing_recipient_phone"

    if is_opted_out and email:
        return "marketing_opt_out_request_exists"

    consent_epoch = _as_epoch(consent_at)
    consent_fresh = consent_epoch > 0 and now_epoch <= (consent_epoch + (consent_renewal_days * 86400))
    if not consent_fresh:
        return "missing_or_expired_marketing_consent"
    if not consent_terms_accepted:
        return "missing_terms_acceptance_for_marketing"

    if normalized_channel == "email":
        if not consent_email_marketing_accepted:
            return "email_marketing_not_opted_in"
        if not consent_email_present:
            return "missing_email_in_consent_record"
        return None

    if normalized_channel == "whatsapp":
        if not consent_phone_present:
            return "missing_phone_in_consent_record"
        return None

    return None


def _merge_contact(pool: dict[str, dict], *, key: str, name: Optional[str], email: Optional[str], phone: Optional[str], source: str,
                   last_activity_at: Optional[str], marketing_opt_in: bool, client_source: bool,
                   consent_at: Optional[str] = None, consent_terms_accepted: Optional[bool] = None,
                   consent_email_marketing_accepted: Optional[bool] = None,
                   consent_email_present: Optional[bool] = None, consent_phone_present: Optional[bool] = None) -> None:
    row = pool.get(key)
    if not row:
        row = {
            "recipient_key": key,
            "recipient_name": name,
            "email": email,
            "phone": phone,
            "segment": "leads",
            "label_en": "Leads",
            "label_es": "Leads",
            "sources": set(),
            "channels": set(),
            "marketing_opt_in": False,
            "has_client_source": False,
            "last_activity_at": None,
            "latest_consent_at": None,
            "consent_terms_accepted": False,
            "consent_email_marketing_accepted": False,
            "consent_email_present": False,
            "consent_phone_present": False,
            "entity_type": "contact",
        }
        pool[key] = row

    if name and not row.get("recipient_name"):
        row["recipient_name"] = name
    if email and not row.get("email"):
        row["email"] = email
    if phone and not row.get("phone"):
        row["phone"] = phone

    row["sources"].add(source)
    if email:
        row["channels"].add("email")
    if phone:
        row["channels"].add("whatsapp")

    row["marketing_opt_in"] = bool(row.get("marketing_opt_in")) or bool(marketing_opt_in)
    row["has_client_source"] = bool(row.get("has_client_source")) or bool(client_source)

    current_ts = _as_epoch(row.get("last_activity_at"))
    incoming_ts = _as_epoch(last_activity_at)
    if incoming_ts >= current_ts:
        row["last_activity_at"] = last_activity_at

    incoming_consent_ts = _as_epoch(consent_at)
    current_consent_ts = _as_epoch(row.get("latest_consent_at"))
    if incoming_consent_ts > 0 and incoming_consent_ts >= current_consent_ts:
        row["latest_consent_at"] = consent_at
        row["consent_terms_accepted"] = bool(consent_terms_accepted)
        row["consent_email_marketing_accepted"] = bool(consent_email_marketing_accepted)
        row["consent_email_present"] = bool(consent_email_present)
        row["consent_phone_present"] = bool(consent_phone_present)


def _load_contacts_audience(client_id: str) -> list[dict[str, Any]]:
    pool: dict[str, dict[str, Any]] = {}
    consent_renewal_days = _load_marketing_consent_renewal_days(client_id)
    now_epoch = datetime.now(timezone.utc).timestamp()
    client_contacts_for_backfill: list[dict[str, Any]] = []

    appointment_clients = (
        supabase.table("appointment_clients")
        .select("user_name,user_email,user_phone,updated_at,created_at")
        .eq("client_id", client_id)
        .order("updated_at", desc=True)
        .execute()
    )

    for raw in appointment_clients.data or []:
        email = _normalize_email(raw.get("user_email"))
        phone = _normalize_phone(raw.get("user_phone"), client_id=client_id)
        name = _normalize_name(raw.get("user_name"))
        key = _recipient_key(email, phone, name)
        if not key:
            continue
        _merge_contact(
            pool,
            key=key,
            name=name,
            email=email,
            phone=phone,
            source="appointment_clients",
            last_activity_at=raw.get("updated_at") or raw.get("created_at"),
            marketing_opt_in=False,
            client_source=True,
        )
        client_contacts_for_backfill.append({"email": email, "phone": phone})

    appointments = (
        supabase.table("appointments")
        .select("user_name,user_email,user_phone,scheduled_time,created_at")
        .eq("client_id", client_id)
        .order("scheduled_time", desc=True)
        .execute()
    )
    for raw in appointments.data or []:
        email = _normalize_email(raw.get("user_email"))
        phone = _normalize_phone(raw.get("user_phone"), client_id=client_id)
        name = _normalize_name(raw.get("user_name"))
        key = _recipient_key(email, phone, name)
        if not key:
            continue
        _merge_contact(
            pool,
            key=key,
            name=name,
            email=email,
            phone=phone,
            source="appointments",
            last_activity_at=raw.get("scheduled_time") or raw.get("created_at"),
            marketing_opt_in=False,
            client_source=True,
        )
        client_contacts_for_backfill.append({"email": email, "phone": phone})

    try:
        backfill_default_marketing_consents_for_contacts(
            client_id=client_id,
            contacts=client_contacts_for_backfill,
            source="marketing_clients_auto",
        )
    except Exception:
        # Non-blocking: audience should still load even if backfill fails.
        pass

    widget_consents = (
        supabase.table("widget_consents")
        .select("email,phone,accepted_terms,accepted_email_marketing,consent_at")
        .eq("client_id", client_id)
        .order("consent_at", desc=True)
        .execute()
    )
    for raw in widget_consents.data or []:
        email = _normalize_email(raw.get("email"))
        phone = _normalize_phone(raw.get("phone"), client_id=client_id)
        key = _recipient_key(email, phone, None)
        if not key:
            continue
        _merge_contact(
            pool,
            key=key,
            name=None,
            email=email,
            phone=phone,
            source="widget_consents",
            last_activity_at=raw.get("consent_at"),
            marketing_opt_in=bool(raw.get("accepted_email_marketing")),
            client_source=False,
            consent_at=raw.get("consent_at"),
            consent_terms_accepted=bool(raw.get("accepted_terms")),
            consent_email_marketing_accepted=bool(raw.get("accepted_email_marketing")),
            consent_email_present=bool(email),
            consent_phone_present=bool(phone),
        )

    handoff_consents = (
        supabase.table("conversation_handoff_requests")
        .select("contact_name,contact_email,contact_phone,accepted_terms,accepted_email_marketing,created_at")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    for raw in handoff_consents.data or []:
        email = _normalize_email(raw.get("contact_email"))
        phone = _normalize_phone(raw.get("contact_phone"), client_id=client_id)
        name = _normalize_name(raw.get("contact_name"))
        key = _recipient_key(email, phone, name)
        if not key:
            continue
        _merge_contact(
            pool,
            key=key,
            name=name,
            email=email,
            phone=phone,
            source="conversation_handoff_requests",
            last_activity_at=raw.get("created_at"),
            marketing_opt_in=bool(raw.get("accepted_email_marketing")),
            client_source=False,
            consent_at=raw.get("created_at"),
            consent_terms_accepted=bool(raw.get("accepted_terms")),
            consent_email_marketing_accepted=bool(raw.get("accepted_email_marketing")),
            consent_email_present=bool(email),
            consent_phone_present=bool(phone),
        )

    candidate_emails = [_normalize_email((row or {}).get("email")) for row in pool.values()]
    opted_out_emails = _load_opted_out_emails_for_client(client_id, [e for e in candidate_emails if e])

    items: list[dict[str, Any]] = []
    for _, row in pool.items():
        if row.get("has_client_source"):
            row["segment"] = "clients"
        elif row.get("marketing_opt_in"):
            row["segment"] = "leads"
        else:
            # Keep audience focused on requested labels only.
            continue

        email = _normalize_email(row.get("email"))
        is_opted_out = bool(email and email in opted_out_emails)
        row["is_opted_out"] = is_opted_out
        row["selection_blocked"] = False
        row["selection_blocked_reason"] = None

        # Lead with opt-out should disappear from audience.
        if row.get("segment") == "leads" and is_opted_out:
            continue
        # Client with opt-out should remain visible but blocked/unlinked.
        if row.get("segment") == "clients" and is_opted_out:
            row["selection_blocked"] = True
            row["selection_blocked_reason"] = "opt_out"
            row["opt_out_label_en"] = "Opt-out"
            row["opt_out_label_es"] = "Desvinculado"

        row["policy_reason_email"] = _resolve_marketing_policy_reason(
            channel="email",
            email=email,
            phone=_normalize_phone(row.get("phone"), client_id=client_id),
            is_opted_out=is_opted_out,
            consent_at=row.get("latest_consent_at"),
            consent_terms_accepted=bool(row.get("consent_terms_accepted")),
            consent_email_marketing_accepted=bool(row.get("consent_email_marketing_accepted")),
            consent_email_present=bool(row.get("consent_email_present")),
            consent_phone_present=bool(row.get("consent_phone_present")),
            consent_renewal_days=consent_renewal_days,
            now_epoch=now_epoch,
        )
        row["policy_reason_whatsapp"] = _resolve_marketing_policy_reason(
            channel="whatsapp",
            email=email,
            phone=_normalize_phone(row.get("phone"), client_id=client_id),
            is_opted_out=is_opted_out,
            consent_at=row.get("latest_consent_at"),
            consent_terms_accepted=bool(row.get("consent_terms_accepted")),
            consent_email_marketing_accepted=bool(row.get("consent_email_marketing_accepted")),
            consent_email_present=bool(row.get("consent_email_present")),
            consent_phone_present=bool(row.get("consent_phone_present")),
            consent_renewal_days=consent_renewal_days,
            now_epoch=now_epoch,
        )
        row["consent_missing_or_expired"] = bool(
            row.get("policy_reason_email") == "missing_or_expired_marketing_consent"
            or row.get("policy_reason_whatsapp") == "missing_or_expired_marketing_consent"
        )

        label_en, label_es = _segment_label(row["segment"])
        row["label_en"] = label_en
        row["label_es"] = label_es
        row["sources"] = sorted(list(row.get("sources", set())))
        row["channels"] = sorted(list(row.get("channels", set())))
        row.pop("latest_consent_at", None)
        row.pop("consent_terms_accepted", None)
        row.pop("consent_email_marketing_accepted", None)
        row.pop("consent_email_present", None)
        row.pop("consent_phone_present", None)
        row.setdefault("entity_type", "contact")
        items.append(row)

    return items


def _load_audience(*, client_id: str, q: Optional[str], segment: Optional[str]) -> list[dict[str, Any]]:
    contact_rows = _load_contacts_audience(client_id)
    items = list(contact_rows)

    q_value = (q or "").strip().lower()
    if q_value:
        items = [
            row
            for row in items
            if q_value in str(row.get("recipient_name") or "").lower()
            or q_value in str(row.get("email") or "").lower()
            or q_value in str(row.get("phone") or "").lower()
            or q_value in str(row.get("recipient_key") or "").lower()
        ]

    if segment and segment in ALLOWED_SEGMENTS:
        items = [row for row in items if row.get("segment") == segment]

    items.sort(
        key=lambda row: (
            SEGMENT_ORDER.get(str(row.get("segment") or "leads"), 99),
            -_as_epoch(row.get("last_activity_at")),
            str(row.get("recipient_name") or "").lower(),
        )
    )

    return items


def _load_campaign(client_id: str, campaign_id: str) -> dict[str, Any]:
    res = (
        supabase.table("marketing_campaigns")
        .select("*")
        .eq("id", campaign_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _enrich_campaign_for_ui(row)


def _to_json_response_payload(resp: Any) -> dict[str, Any]:
    if isinstance(resp, JSONResponse):
        try:
            body = resp.body.decode("utf-8") if isinstance(resp.body, (bytes, bytearray)) else resp.body
            parsed = json.loads(body or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    if isinstance(resp, dict):
        return resp
    return {}


def _load_owner_email(auth_user_id: str) -> str:
    try:
        res = (
            supabase.table("users")
            .select("email")
            .eq("id", auth_user_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        email = _normalize_email(row.get("email"))
        return email or "support@evolvianai.com"
    except Exception:
        return "support@evolvianai.com"


def _load_company_postal_address(client_id: str) -> str:
    try:
        res = (
            supabase.table("client_profile")
            .select("address,city,state,postal_code,country")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        parts = [
            str(row.get("address") or "").strip(),
            str(row.get("city") or "").strip(),
            str(row.get("state") or "").strip(),
            str(row.get("postal_code") or "").strip(),
            str(row.get("country") or "").strip(),
        ]
        cleaned = [part for part in parts if part]
        if cleaned:
            return ", ".join(cleaned)
    except Exception:
        pass
    return "Address not configured"


def _build_unsubscribe_url(base_url: Optional[str], email: str, client_id: str) -> str:
    api_base = (
        os.getenv("EVOLVIAN_API_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://evolvianai.com"
    ).strip().rstrip("/")
    default_base = f"{api_base}/api/public/privacy/unsubscribe"
    base = (base_url or os.getenv("EVOLVIAN_MARKETING_UNSUBSCRIBE_BASE_URL") or default_base).strip()
    separator = "&" if "?" in base else "?"
    encrypted_client_id = encrypt_unsubscribe_client_id(client_id)
    return f"{base}{separator}email={quote_plus(email)}&client_id={quote_plus(encrypted_client_id)}"


def _render_campaign_html(
    campaign: dict[str, Any],
    recipient: dict[str, Any],
    *,
    cta_url_override: Optional[str] = None,
) -> str:
    body = str(campaign.get("body") or "").strip().replace("\n", "<br />\n")
    image_url = str(campaign.get("image_url") or "").strip()
    cta_mode = str(campaign.get("cta_mode") or "").strip().lower()
    cta_label = str(campaign.get("cta_label") or "").strip() or "Open"
    cta_url = _normalize_redirect_url(cta_url_override) or _normalize_redirect_url(campaign.get("cta_url")) or ""
    recipient_name = str(recipient.get("recipient_name") or "").strip()

    lines = [f"<p>{body}</p>"]
    if recipient_name:
        lines.insert(0, f"<p>Hi {recipient_name},</p>")

    if image_url:
        lines.append(
            f"<p><img src='{image_url}' alt='campaign' style='max-width:100%;height:auto;border-radius:10px;' /></p>"
        )

    if cta_url:
        lines.append(
            f"<p><a href='{cta_url}' style='display:inline-block;padding:10px 16px;border-radius:8px;background:#1f6feb;color:#fff;text-decoration:none;'>{cta_label}</a></p>"
        )

    return "\n".join(lines)


def _upsert_campaign_recipient(payload: dict[str, Any]) -> dict[str, Any]:
    res = (
        supabase.table("marketing_campaign_recipients")
        .upsert(payload, on_conflict="campaign_id,recipient_key")
        .execute()
    )
    return (res.data or [None])[0] or payload


def _log_campaign_event(*, client_id: str, campaign_id: str, recipient_key: str, event_type: str, metadata: Optional[dict[str, Any]] = None) -> None:
    try:
        supabase.table("marketing_campaign_events").insert(
            {
                "client_id": client_id,
                "campaign_id": campaign_id,
                "recipient_key": recipient_key,
                "event_type": event_type,
                "metadata": metadata or {},
                "created_at": _now_iso(),
            }
        ).execute()
    except Exception:
        # Non-blocking audit write.
        return


@router.get("/audience")
def get_marketing_audience(
    request: Request,
    client_id: str = Query(...),
    q: Optional[str] = Query(None),
    segment: Optional[Literal["clients", "leads"]] = Query(None),
):
    try:
        authorize_client_request(request, client_id)
        _ensure_premium_access(client_id)
        rows = _load_audience(client_id=client_id, q=q, segment=segment)

        counts = {"clients": 0, "leads": 0}
        for row in rows:
            key = str(row.get("segment") or "")
            if key in counts:
                counts[key] += 1

        return {
            "items": rows,
            "counts": counts,
        }
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail="Failed loading marketing audience")


@router.get("/audience/history")
def get_marketing_history_for_recipient(
    request: Request,
    client_id: str = Query(...),
    recipient_key: str = Query(...),
):
    try:
        authorize_client_request(request, client_id)
        _ensure_premium_access(client_id)

        rows_res = (
            supabase.table("marketing_campaign_recipients")
            .select("campaign_id,recipient_key,send_status,provider_message_id,policy_proof_id,send_error,sent_at,updated_at,segment")
            .eq("client_id", client_id)
            .eq("recipient_key", recipient_key)
            .order("updated_at", desc=True)
            .limit(200)
            .execute()
        )
        rows = rows_res.data or []
        if not rows:
            return {"items": []}

        campaign_ids = sorted({str(row.get("campaign_id")) for row in rows if row.get("campaign_id")})
        campaigns_res = (
            supabase.table("marketing_campaigns")
            .select("id,name,channel,status,created_at,last_sent_at")
            .eq("client_id", client_id)
            .in_("id", campaign_ids)
            .execute()
        )
        campaigns = {str(row.get("id")): row for row in (campaigns_res.data or []) if row.get("id")}

        items = []
        for row in rows:
            campaign = campaigns.get(str(row.get("campaign_id")))
            if not campaign:
                continue
            items.append(
                {
                    "campaign_id": row.get("campaign_id"),
                    "campaign_name": campaign.get("name"),
                    "campaign_channel": campaign.get("channel"),
                    "campaign_status": campaign.get("status"),
                    "send_status": row.get("send_status"),
                    "provider_message_id": row.get("provider_message_id"),
                    "policy_proof_id": row.get("policy_proof_id"),
                    "send_error": row.get("send_error"),
                    "sent_at": row.get("sent_at"),
                    "updated_at": row.get("updated_at"),
                }
            )

        return {"items": items}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail="Failed loading recipient campaign history")


@router.get("/campaigns")
def list_campaigns(
    request: Request,
    client_id: str = Query(...),
    q: Optional[str] = Query(None),
    channel: Optional[Literal["email", "whatsapp"]] = Query(None),
    status: Optional[str] = Query(None),
    include_archived: bool = Query(False),
):
    try:
        authorize_client_request(request, client_id)
        _ensure_premium_access(client_id)

        query = (
            supabase.table("marketing_campaigns")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
        )
        if not include_archived:
            query = query.eq("is_active", True)
        if channel:
            query = query.eq("channel", channel)
        if status:
            query = query.eq("status", status)

        rows = query.execute().data or []
        q_value = (q or "").strip().lower()
        if q_value:
            rows = [
                row
                for row in rows
                if q_value in str(row.get("name") or "").lower()
                or q_value in str(row.get("subject") or "").lower()
                or q_value in str(row.get("body") or "").lower()
            ]

        return {"items": [_enrich_campaign_for_ui(row) for row in rows]}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail="Failed loading campaigns")


@router.get("/campaigns/{campaign_id}")
def get_campaign_detail(request: Request, campaign_id: str, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)
        _ensure_premium_access(client_id)

        campaign = _load_campaign(client_id, campaign_id)
        recipients_res = (
            supabase.table("marketing_campaign_recipients")
            .select("*")
            .eq("client_id", client_id)
            .eq("campaign_id", campaign_id)
            .order("updated_at", desc=True)
            .limit(2000)
            .execute()
        )

        return {
            "campaign": campaign,
            "recipients": recipients_res.data or [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail="Failed loading campaign detail")


@router.post("/campaigns")
def create_campaign(request: Request, payload: CampaignCreatePayload):
    try:
        auth_user_id = authorize_client_request(request, payload.client_id)
        _ensure_premium_access(payload.client_id)
        raw_cta_url = str(payload.cta_url or "").strip()
        normalized_cta_url = _normalize_redirect_url(raw_cta_url)
        if raw_cta_url and not normalized_cta_url:
            raise HTTPException(status_code=400, detail="Invalid CTA URL. Use an absolute http(s) URL.")
        normalized_cta_label = str(payload.cta_label or "").strip() or None
        normalized_cta_mode = "url" if normalized_cta_url else None
        if not normalized_cta_url:
            normalized_cta_label = None

        insert_payload = {
            "client_id": payload.client_id,
            "name": payload.name,
            "channel": payload.channel,
            "status": payload.status or "draft",
            "subject": payload.subject,
            "body": payload.body,
            "image_url": payload.image_url,
            "cta_mode": normalized_cta_mode,
            "cta_label": normalized_cta_label,
            "cta_url": normalized_cta_url,
            "language_family": payload.language_family or "es",
            "template_id": None,
            "meta_template_id": None,
            "meta_template_name": None,
            "created_by_user_id": auth_user_id,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "is_active": True,
        }

        result = supabase.table("marketing_campaigns").insert(insert_payload).execute()
        row = (result.data or [None])[0]
        if not row:
            raise HTTPException(status_code=500, detail="Could not create campaign")

        campaign_id = str(row.get("id") or "").strip()
        if not campaign_id:
            raise HTTPException(status_code=500, detail="Could not resolve campaign id")

        template_updates: dict[str, Any] = {}
        if payload.channel == "email":
            normalized_payload = payload.model_copy(
                update={
                    "cta_mode": normalized_cta_mode,
                    "cta_url": normalized_cta_url,
                    "cta_label": normalized_cta_label,
                    "whatsapp_interest_enabled": None,
                    "whatsapp_interest_label": None,
                    "whatsapp_opt_out_enabled": None,
                    "whatsapp_opt_out_label": None,
                }
            )
            email_template = _create_email_template_for_campaign(payload.client_id, normalized_payload)
            template_updates["template_id"] = email_template.get("id")
        else:
            normalized_payload = payload.model_copy(
                update={
                    "cta_mode": normalized_cta_mode,
                    "cta_url": normalized_cta_url,
                    "cta_label": normalized_cta_label,
                    "whatsapp_interest_enabled": (
                        True if payload.whatsapp_interest_enabled is None else bool(payload.whatsapp_interest_enabled)
                    ),
                    "whatsapp_interest_label": _normalize_whatsapp_interest_label(
                        payload.whatsapp_interest_label,
                        payload.language_family,
                    ),
                    "whatsapp_opt_out_enabled": (
                        True if payload.whatsapp_opt_out_enabled is None else bool(payload.whatsapp_opt_out_enabled)
                    ),
                    "whatsapp_opt_out_label": _normalize_whatsapp_opt_out_label(
                        payload.whatsapp_opt_out_label,
                        payload.language_family,
                    ),
                }
            )
            wa_templates = _create_whatsapp_template_for_campaign(
                payload.client_id,
                normalized_payload,
                campaign_id=campaign_id,
            )
            template_updates["template_id"] = wa_templates["message_template"].get("id")
            template_updates["meta_template_id"] = wa_templates["meta"].get("id")
            template_updates["meta_template_name"] = wa_templates.get("meta_template_name")

        if template_updates:
            template_updates["updated_at"] = _now_iso()
            update_res = (
                supabase.table("marketing_campaigns")
                .update(template_updates)
                .eq("id", campaign_id)
                .eq("client_id", payload.client_id)
                .execute()
            )
            updated_row = (update_res.data or [None])[0]
            if updated_row:
                row = updated_row

        return {"campaign": _enrich_campaign_for_ui(row)}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail=f"Failed creating campaign: {exc}")


@router.post("/campaigns/rewrite")
def rewrite_campaign_content(request: Request, payload: CampaignRewritePayload):
    try:
        authorize_client_request(request, payload.client_id)
        _ensure_premium_access(payload.client_id)

        rewritten = _rewrite_campaign_body(payload)
        return {
            "success": True,
            "rewritten_body": rewritten,
            "provider": "openai",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed rewriting campaign content: {exc}")


@router.patch("/campaigns/{campaign_id}")
def update_campaign(request: Request, campaign_id: str, payload: CampaignUpdatePayload):
    try:
        authorize_client_request(request, payload.client_id)
        _ensure_premium_access(payload.client_id)

        campaign = _load_campaign(payload.client_id, campaign_id)

        updates = {}
        for field in [
            "name",
            "subject",
            "body",
            "image_url",
            "cta_mode",
            "cta_label",
            "cta_url",
            "language_family",
            "status",
        ]:
            value = getattr(payload, field)
            if value is not None:
                updates[field] = value

        if "cta_url" in updates:
            raw_update_url = str(updates.get("cta_url") or "").strip()
            updates["cta_url"] = _normalize_redirect_url(raw_update_url)
            if raw_update_url and not updates["cta_url"]:
                raise HTTPException(status_code=400, detail="Invalid CTA URL. Use an absolute http(s) URL.")
        if "cta_label" in updates:
            updates["cta_label"] = str(updates.get("cta_label") or "").strip() or None
        if "cta_mode" in updates or "cta_url" in updates:
            effective_url = updates.get("cta_url") if "cta_url" in updates else _normalize_redirect_url(campaign.get("cta_url"))
            updates["cta_mode"] = "url" if effective_url else None
            if not effective_url:
                updates["cta_label"] = None

        normalized_interest_label = None
        if payload.whatsapp_interest_label is not None:
            normalized_interest_label = _normalize_whatsapp_interest_label(
                payload.whatsapp_interest_label,
                updates.get("language_family") if "language_family" in updates else campaign.get("language_family"),
            )

        normalized_opt_out_label = None
        if payload.whatsapp_opt_out_label is not None:
            normalized_opt_out_label = _normalize_whatsapp_opt_out_label(
                payload.whatsapp_opt_out_label,
                updates.get("language_family") if "language_family" in updates else campaign.get("language_family"),
            )

        should_version_whatsapp_template = False
        if str(campaign.get("channel") or "") == "whatsapp":
            touched_fields = {
                "name",
                "body",
                "language_family",
                "cta_mode",
                "cta_label",
                "cta_url",
                "image_url",
            }
            should_version_whatsapp_template = any(field in updates for field in touched_fields)
            if payload.whatsapp_opt_out_enabled is not None:
                current_enabled = bool(campaign.get("whatsapp_opt_out_enabled"))
                if bool(payload.whatsapp_opt_out_enabled) != current_enabled:
                    should_version_whatsapp_template = True
            if payload.whatsapp_interest_enabled is not None:
                current_interest_enabled = bool(campaign.get("whatsapp_interest_enabled", True))
                if bool(payload.whatsapp_interest_enabled) != current_interest_enabled:
                    should_version_whatsapp_template = True
            if payload.whatsapp_interest_label is not None:
                current_interest_label = _normalize_whatsapp_interest_label(
                    campaign.get("whatsapp_interest_label"),
                    updates.get("language_family") if "language_family" in updates else campaign.get("language_family"),
                )
                if normalized_interest_label != current_interest_label:
                    should_version_whatsapp_template = True
            if payload.whatsapp_opt_out_label is not None:
                current_label = _normalize_whatsapp_opt_out_label(
                    campaign.get("whatsapp_opt_out_label"),
                    updates.get("language_family") if "language_family" in updates else campaign.get("language_family"),
                )
                if normalized_opt_out_label != current_label:
                    should_version_whatsapp_template = True

        if should_version_whatsapp_template:
            merged_cta_url = updates.get("cta_url") if "cta_url" in updates else _normalize_redirect_url(campaign.get("cta_url"))
            merged_cta_label = updates.get("cta_label") if "cta_label" in updates else (str(campaign.get("cta_label") or "").strip() or None)
            merged_cta_mode = "url" if merged_cta_url else None
            if not merged_cta_url:
                merged_cta_label = None
            merged_language = (
                updates.get("language_family") if "language_family" in updates else campaign.get("language_family")
            ) or "es"
            merged_interest_enabled = (
                bool(payload.whatsapp_interest_enabled)
                if payload.whatsapp_interest_enabled is not None
                else bool(campaign.get("whatsapp_interest_enabled", True))
            )
            merged_interest_label = (
                normalized_interest_label
                if normalized_interest_label is not None
                else _normalize_whatsapp_interest_label(
                    campaign.get("whatsapp_interest_label"),
                    merged_language,
                )
            )
            merged_opt_out_enabled = (
                bool(payload.whatsapp_opt_out_enabled)
                if payload.whatsapp_opt_out_enabled is not None
                else bool(campaign.get("whatsapp_opt_out_enabled", True))
            )
            merged_opt_out_label = (
                normalized_opt_out_label
                if normalized_opt_out_label is not None
                else _normalize_whatsapp_opt_out_label(
                    campaign.get("whatsapp_opt_out_label"),
                    merged_language,
                )
            )
            merged = CampaignCreatePayload(
                client_id=payload.client_id,
                name=str(updates.get("name") or campaign.get("name") or "Campaign"),
                channel="whatsapp",
                subject=str(updates.get("subject") or campaign.get("subject") or ""),
                body=str(updates.get("body") or campaign.get("body") or ""),
                image_url=updates.get("image_url") if "image_url" in updates else campaign.get("image_url"),
                cta_mode=merged_cta_mode,
                cta_label=merged_cta_label,
                cta_url=merged_cta_url,
                language_family=merged_language,
                whatsapp_interest_enabled=merged_interest_enabled,
                whatsapp_interest_label=merged_interest_label,
                whatsapp_opt_out_enabled=merged_opt_out_enabled,
                whatsapp_opt_out_label=merged_opt_out_label,
            )
            wa_templates = _create_whatsapp_template_for_campaign(
                payload.client_id,
                merged,
                campaign_id=campaign_id,
            )
            updates["template_id"] = wa_templates["message_template"].get("id")
            updates["meta_template_id"] = wa_templates["meta"].get("id")
            updates["meta_template_name"] = wa_templates.get("meta_template_name")
        elif str(campaign.get("channel") or "") == "email":
            touched_fields = {"name", "body", "image_url", "cta_mode", "cta_label", "cta_url", "language_family"}
            should_refresh_email_snapshot = any(field in updates for field in touched_fields)
            if should_refresh_email_snapshot:
                merged_body = str(updates.get("body") if "body" in updates else campaign.get("body") or "")
                merged_image_url = str(updates.get("image_url") if "image_url" in updates else campaign.get("image_url") or "").strip() or None
                merged_cta_url = (
                    updates.get("cta_url")
                    if "cta_url" in updates
                    else _normalize_redirect_url(campaign.get("cta_url"))
                )
                merged_cta_label = str(updates.get("cta_label") if "cta_label" in updates else campaign.get("cta_label") or "").strip() or None
                merged_language = str(
                    updates.get("language_family") if "language_family" in updates else campaign.get("language_family") or "es"
                ).strip().lower() or "es"
                if not merged_cta_url:
                    merged_cta_label = None

                rendered = _build_email_template_body(
                    body_text=merged_body,
                    image_url=merged_image_url,
                    cta_mode="url" if merged_cta_url else None,
                    cta_label=merged_cta_label,
                    cta_url=merged_cta_url,
                )

                template_id = str(campaign.get("template_id") or "").strip()
                if template_id:
                    template_updates = {
                        "label": str(updates.get("name") if "name" in updates else campaign.get("name") or "Campaign"),
                        "body": rendered,
                        "language_family": merged_language,
                        "locale_code": _format_locale(merged_language),
                        "updated_at": _now_iso(),
                    }
                    try:
                        (
                            supabase.table("message_templates")
                            .update(template_updates)
                            .eq("id", template_id)
                            .eq("client_id", payload.client_id)
                            .execute()
                        )
                    except Exception:
                        # Snapshot update should not block campaign edit.
                        pass

        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")

        updates["updated_at"] = _now_iso()
        result = (
            supabase.table("marketing_campaigns")
            .update(updates)
            .eq("id", campaign_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        row = (result.data or [None])[0]
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"campaign": _enrich_campaign_for_ui(row)}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail=f"Failed updating campaign: {exc}")


@router.delete("/campaigns/{campaign_id}")
def archive_campaign(request: Request, campaign_id: str, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)
        _ensure_premium_access(client_id)

        campaign = _load_campaign(client_id, campaign_id)
        if not bool(campaign.get("is_active", True)):
            return {"campaign": campaign, "archived": True}

        updates = {
            "status": "archived",
            "is_active": False,
            "updated_at": _now_iso(),
        }
        result = (
            supabase.table("marketing_campaigns")
            .update(updates)
            .eq("id", campaign_id)
            .eq("client_id", client_id)
            .execute()
        )
        row = (result.data or [None])[0]
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        template_id = str(campaign.get("template_id") or "").strip()
        if template_id:
            try:
                (
                    supabase.table("message_templates")
                    .update({"is_active": False, "updated_at": _now_iso()})
                    .eq("id", template_id)
                    .eq("client_id", client_id)
                    .execute()
                )
            except Exception:
                # Non-blocking cleanup to keep archive flow robust.
                pass

        return {"campaign": row, "archived": True}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail=f"Failed archiving campaign: {exc}")


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(request: Request, campaign_id: str, payload: CampaignSendPayload):
    try:
        auth_user_id = authorize_client_request(request, payload.client_id)
        _ensure_premium_access(payload.client_id)

        campaign = _load_campaign(payload.client_id, campaign_id)
        if not bool(campaign.get("is_active", True)):
            raise HTTPException(status_code=409, detail="Campaign is archived/inactive")
        if str(campaign.get("channel") or "").lower() == "whatsapp":
            _ensure_whatsapp_channel_connected(payload.client_id)

        audience = _load_audience(client_id=payload.client_id, q=None, segment=None)
        audience_by_key = {str(row.get("recipient_key")): row for row in audience if row.get("recipient_key")}

        targets: list[dict[str, Any]] = []
        if payload.recipient_keys is not None and len(payload.recipient_keys) == 0:
            raise HTTPException(status_code=400, detail="Recipient selection cannot be empty.")

        has_explicit_selection = payload.recipient_keys is not None or bool(payload.segment_filters)
        if not has_explicit_selection:
            raise HTTPException(status_code=400, detail="Recipient selection is required before sending.")

        if payload.recipient_keys:
            for key in payload.recipient_keys:
                item = audience_by_key.get(str(key or "").strip())
                if item:
                    targets.append(item)
        else:
            targets = list(audience_by_key.values())

        if payload.segment_filters:
            filters = {str(seg) for seg in payload.segment_filters if str(seg) in ALLOWED_SEGMENTS}
            targets = [row for row in targets if str(row.get("segment")) in filters]

        blocked_selection = [row for row in targets if bool(row.get("selection_blocked"))]
        if blocked_selection:
            summary_skipped = len(blocked_selection)
            targets = [row for row in targets if not bool(row.get("selection_blocked"))]
        else:
            summary_skipped = 0

        if campaign.get("channel") == "email":
            targets = [row for row in targets if row.get("email")]
        elif campaign.get("channel") == "whatsapp":
            targets = [row for row in targets if row.get("phone")]

        targets = targets[: payload.limit]

        summary = {
            "total_targets": len(targets),
            "sent": 0,
            "failed": 0,
            "blocked_policy": 0,
            "skipped": summary_skipped,
            "dry_run": bool(payload.dry_run),
            "image_fallback_no_header": 0,
            "image_skipped_no_header_template": 0,
            "button_fallback_no_url_param": 0,
        }
        campaign_image_url = str(campaign.get("image_url") or "").strip() or None
        campaign_has_url_button = bool(campaign.get("whatsapp_has_url_button"))
        campaign_whatsapp_param = str(campaign.get("body") or "").strip() or (
            "We have updates for you." if str(campaign.get("language_family") or "").lower().startswith("en") else "Tenemos novedades para ti."
        )

        company_postal_address = _load_company_postal_address(payload.client_id)
        owner_email = _load_owner_email(auth_user_id)

        for target in targets:
            recipient_key = str(target.get("recipient_key") or "").strip()
            if not recipient_key:
                continue

            base_row = {
                "client_id": payload.client_id,
                "campaign_id": campaign_id,
                "recipient_key": recipient_key,
                "recipient_name": target.get("recipient_name"),
                "email": target.get("email"),
                "phone": target.get("phone"),
                "segment": target.get("segment"),
                "send_status": "pending",
                "updated_at": _now_iso(),
            }

            if payload.dry_run:
                _upsert_campaign_recipient(base_row)
                summary["skipped"] += 1
                continue

            if campaign.get("channel") == "email":
                recipient_email = _normalize_email(target.get("email"))
                if not recipient_email:
                    base_row.update({"send_status": "skipped", "send_error": "missing_email"})
                    _upsert_campaign_recipient(base_row)
                    summary["skipped"] += 1
                    continue

                unsubscribe_url = _build_unsubscribe_url(payload.unsubscribe_base_url, recipient_email, payload.client_id)
                tracking_cta_url = (
                    _build_campaign_interest_tracking_url(
                        campaign_id=campaign_id,
                        channel="email",
                        recipient_key=recipient_key,
                    )
                    if _normalize_redirect_url(campaign.get("cta_url"))
                    else None
                )

                # Lazy import to avoid optional-module import failures during startup.
                from api.modules.email_integration.gmail_oauth import send_reply as gmail_send_reply

                email_payload = {
                    "client_id": payload.client_id,
                    "to_email": recipient_email,
                    "subject": campaign.get("subject") or campaign.get("name") or "Marketing campaign",
                    "html": _render_campaign_html(campaign, target, cta_url_override=tracking_cta_url),
                    "purpose": "marketing",
                    "campaign_id": campaign_id,
                    "campaign_owner_email": owner_email,
                    "unsubscribe_url": unsubscribe_url,
                    "company_postal_address": company_postal_address,
                    "policy_source": "marketing_campaign_send",
                    "source_id": campaign_id,
                }

                try:
                    send_resp = await gmail_send_reply(email_payload, request)
                    send_json = _to_json_response_payload(send_resp)

                    provider_message_id = send_json.get("message_id")
                    base_row.update(
                        {
                            "send_status": "sent",
                            "provider": "gmail",
                            "provider_message_id": provider_message_id,
                            "sent_at": _now_iso(),
                            "send_error": None,
                            "policy_proof_id": None,
                        }
                    )
                    _upsert_campaign_recipient(base_row)
                    _log_campaign_event(
                        client_id=payload.client_id,
                        campaign_id=campaign_id,
                        recipient_key=recipient_key,
                        event_type="sent",
                        metadata={"provider": "gmail", "provider_message_id": provider_message_id},
                    )
                    summary["sent"] += 1
                except HTTPException as exc:
                    detail = exc.detail
                    if isinstance(detail, dict) and detail.get("code") == "OUTBOUND_POLICY_BLOCKED":
                        base_row.update(
                            {
                                "send_status": "blocked_policy",
                                "send_error": detail.get("reason"),
                                "policy_proof_id": detail.get("proof_id"),
                                "provider": "gmail",
                            }
                        )
                        summary["blocked_policy"] += 1
                    else:
                        base_row.update(
                            {
                                "send_status": "failed",
                                "send_error": str(detail),
                                "provider": "gmail",
                            }
                        )
                        summary["failed"] += 1
                    _upsert_campaign_recipient(base_row)
                    _log_campaign_event(
                        client_id=payload.client_id,
                        campaign_id=campaign_id,
                        recipient_key=recipient_key,
                        event_type=base_row["send_status"],
                        metadata={"error": base_row.get("send_error"), "policy_proof_id": base_row.get("policy_proof_id")},
                    )

            else:
                raw_phone = str(target.get("phone") or "").strip()
                recipient_phone = _normalize_phone(raw_phone, client_id=payload.client_id)
                if not recipient_phone:
                    base_row.update(
                        {
                            "send_status": "skipped",
                            "send_error": "invalid_phone_format" if raw_phone else "missing_phone",
                        }
                    )
                    _upsert_campaign_recipient(base_row)
                    summary["skipped"] += 1
                    continue

                template_name = str(campaign.get("meta_template_name") or "").strip()
                if not template_name:
                    base_row.update({"send_status": "failed", "send_error": "missing_meta_template_name"})
                    _upsert_campaign_recipient(base_row)
                    summary["failed"] += 1
                    continue

                language_code = _format_locale(campaign.get("language_family"))
                template_has_header = bool(campaign.get("whatsapp_has_image_header"))
                header_image_url = campaign_image_url if template_has_header else None
                button_url_parameters = (
                    [quote_plus(recipient_key)]
                    if (_normalize_redirect_url(campaign.get("cta_url")) and campaign_has_url_button)
                    else None
                )
                if campaign_image_url and not template_has_header:
                    summary["image_skipped_no_header_template"] += 1
                send_result = await send_whatsapp_template_for_client(
                    client_id=payload.client_id,
                    to_number=recipient_phone,
                    template_name=template_name,
                    parameters=[campaign_whatsapp_param],
                    button_url_parameters=button_url_parameters,
                    header_image_url=header_image_url,
                    language_code=language_code,
                    purpose="marketing",
                    recipient_email=_normalize_email(target.get("email")),
                    policy_source="marketing_campaign_send",
                    policy_source_id=campaign_id,
                )
                header_fallback_used = False
                button_fallback_no_url_param = False
                if (
                    not send_result.get("success")
                    and button_url_parameters
                    and _is_meta_template_parameter_error(send_result.get("error"))
                ):
                    send_result = await send_whatsapp_template_for_client(
                        client_id=payload.client_id,
                        to_number=recipient_phone,
                        template_name=template_name,
                        parameters=[campaign_whatsapp_param],
                        button_url_parameters=None,
                        header_image_url=header_image_url,
                        language_code=language_code,
                        purpose="marketing",
                        recipient_email=_normalize_email(target.get("email")),
                        policy_source="marketing_campaign_send",
                        policy_source_id=campaign_id,
                    )
                    button_fallback_no_url_param = bool(send_result.get("success"))
                    if button_fallback_no_url_param:
                        summary["button_fallback_no_url_param"] += 1
                        campaign_has_url_button = False
                        _disable_meta_template_url_buttons(campaign.get("meta_template_id"))
                if not send_result.get("success") and header_image_url:
                    raw_error_probe = str(send_result.get("error") or "").lower()
                    if (
                        "header" in raw_error_probe
                        or "component" in raw_error_probe
                        or "parameter" in raw_error_probe
                    ):
                        send_result = await send_whatsapp_template_for_client(
                            client_id=payload.client_id,
                            to_number=recipient_phone,
                            template_name=template_name,
                            parameters=[campaign_whatsapp_param],
                            button_url_parameters=button_url_parameters,
                            header_image_url=None,
                            language_code=language_code,
                            purpose="marketing",
                            recipient_email=_normalize_email(target.get("email")),
                            policy_source="marketing_campaign_send",
                            policy_source_id=campaign_id,
                        )
                        header_fallback_used = bool(send_result.get("success"))
                        if header_fallback_used:
                            summary["image_fallback_no_header"] += 1
                            _disable_meta_template_header(campaign.get("meta_template_id"))

                if send_result.get("success"):
                    base_row.update(
                        {
                            "send_status": "sent",
                            "provider": "meta",
                            "provider_message_id": send_result.get("meta_message_id"),
                            "policy_proof_id": send_result.get("policy_proof_id"),
                            "sent_at": _now_iso(),
                        }
                    )
                    _upsert_campaign_recipient(base_row)
                    _log_campaign_event(
                        client_id=payload.client_id,
                        campaign_id=campaign_id,
                        recipient_key=recipient_key,
                        event_type="sent",
                        metadata={
                            "provider": "meta",
                            "provider_message_id": send_result.get("meta_message_id"),
                            "policy_proof_id": send_result.get("policy_proof_id"),
                            "header_fallback_no_image": header_fallback_used,
                            "button_fallback_no_url_param": button_fallback_no_url_param,
                            "header_template_missing": bool(campaign_image_url and not template_has_header),
                        },
                    )
                    summary["sent"] += 1
                else:
                    raw_error = str(send_result.get("error") or "provider_send_failed")
                    is_policy = raw_error.startswith("policy_blocked:")
                    base_row.update(
                        {
                            "send_status": "blocked_policy" if is_policy else "failed",
                            "send_error": raw_error.replace("policy_blocked:", "", 1) if is_policy else raw_error,
                            "policy_proof_id": send_result.get("policy_proof_id"),
                            "provider": "meta",
                        }
                    )
                    _upsert_campaign_recipient(base_row)
                    _log_campaign_event(
                        client_id=payload.client_id,
                        campaign_id=campaign_id,
                        recipient_key=recipient_key,
                        event_type=base_row["send_status"],
                        metadata={"error": base_row.get("send_error"), "policy_proof_id": base_row.get("policy_proof_id")},
                    )
                    if is_policy:
                        summary["blocked_policy"] += 1
                    else:
                        summary["failed"] += 1

        final_status = campaign.get("status")
        if not payload.dry_run and summary["sent"] > 0:
            final_status = "sent"
        elif not payload.dry_run and summary["failed"] > 0 and summary["sent"] == 0:
            final_status = "active"

        update_payload = {
            "status": final_status,
            "updated_at": _now_iso(),
            "last_sent_at": _now_iso() if not payload.dry_run else campaign.get("last_sent_at"),
            "send_count": int(campaign.get("send_count") or 0) + int(summary["sent"]),
        }
        (
            supabase.table("marketing_campaigns")
            .update(update_payload)
            .eq("id", campaign_id)
            .eq("client_id", payload.client_id)
            .execute()
        )

        return {
            "campaign_id": campaign_id,
            "summary": summary,
            "status": final_status,
        }

    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_marketing_tables(exc):
            raise HTTPException(
                status_code=503,
                detail="Marketing tables are not available yet. Run docs/sql/2026-02-27_marketing_campaigns.sql first.",
            )
        raise HTTPException(status_code=500, detail=f"Failed sending campaign: {exc}")
