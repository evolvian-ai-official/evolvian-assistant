from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional


logger = logging.getLogger(__name__)

MARKETING_CONTACTS_TABLE = "marketing_contacts"
VALID_INTEREST_STATUSES = {"interested", "not_interested", "unknown"}


def normalize_marketing_email(value: Any) -> Optional[str]:
    cleaned = str(value or "").strip().lower()
    return cleaned or None


def normalize_marketing_phone(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    if digits.startswith("521") and len(digits) == 13:
        digits = "52" + digits[3:]
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}"


def _coerce_bool(value: Any) -> bool:
    return bool(value)


def _normalize_interest_status(value: Any) -> str:
    normalized = str(value or "unknown").strip().lower()
    return normalized if normalized in VALID_INTEREST_STATUSES else "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_epoch(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def _load_existing_contact(
    *,
    supabase_client: Any,
    client_id: str,
    normalized_email: str | None,
    normalized_phone: str | None,
) -> dict[str, Any] | None:
    if normalized_email:
        rows = (
            supabase_client.table(MARKETING_CONTACTS_TABLE)
            .select(
                "id,name,email,normalized_email,phone,normalized_phone,"
                "email_opt_in,whatsapp_opt_in,email_unsubscribed,whatsapp_unsubscribed,"
                "interest_status,first_seen_at,last_seen_at"
            )
            .eq("client_id", client_id)
            .eq("normalized_email", normalized_email)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            return rows[0] or None

    if normalized_phone:
        rows = (
            supabase_client.table(MARKETING_CONTACTS_TABLE)
            .select(
                "id,name,email,normalized_email,phone,normalized_phone,"
                "email_opt_in,whatsapp_opt_in,email_unsubscribed,whatsapp_unsubscribed,"
                "interest_status,first_seen_at,last_seen_at"
            )
            .eq("client_id", client_id)
            .eq("normalized_phone", normalized_phone)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            return rows[0] or None

    return None


def upsert_marketing_contact_state(
    *,
    supabase_client: Any,
    client_id: str | None,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    email_opt_in: bool | None = None,
    whatsapp_opt_in: bool | None = None,
    email_unsubscribed: bool | None = None,
    whatsapp_unsubscribed: bool | None = None,
    interest_status: str | None = None,
    seen_at: str | None = None,
) -> bool:
    normalized_client_id = str(client_id or "").strip()
    normalized_email = normalize_marketing_email(email)
    normalized_phone = normalize_marketing_phone(phone)
    normalized_name = str(name or "").strip() or None
    effective_seen_at = str(seen_at or "").strip() or _now_iso()
    incoming_interest = _normalize_interest_status(interest_status)

    if not normalized_client_id or (not normalized_email and not normalized_phone):
        return False

    try:
        existing = _load_existing_contact(
            supabase_client=supabase_client,
            client_id=normalized_client_id,
            normalized_email=normalized_email,
            normalized_phone=normalized_phone,
        )
    except Exception:
        logger.exception(
            "Failed loading marketing contact | client_id=%s | email=%s | phone=%s",
            normalized_client_id,
            normalized_email,
            normalized_phone,
        )
        return False

    if existing:
        existing_last_seen_at = existing.get("last_seen_at")
        incoming_is_newer = _as_epoch(effective_seen_at) >= _as_epoch(existing_last_seen_at)
        current_interest = _normalize_interest_status(existing.get("interest_status"))
        merged_interest = current_interest
        if incoming_interest != "unknown" and incoming_is_newer:
            merged_interest = incoming_interest
        payload = {
            "name": normalized_name or existing.get("name"),
            "email": normalized_email or existing.get("email"),
            "normalized_email": normalized_email or existing.get("normalized_email"),
            "phone": normalized_phone or existing.get("phone"),
            "normalized_phone": normalized_phone or existing.get("normalized_phone"),
            "email_opt_in": (
                _coerce_bool(email_opt_in)
                if incoming_is_newer and email_opt_in is not None
                else _coerce_bool(existing.get("email_opt_in"))
            ),
            "whatsapp_opt_in": (
                _coerce_bool(whatsapp_opt_in)
                if incoming_is_newer and whatsapp_opt_in is not None
                else _coerce_bool(existing.get("whatsapp_opt_in"))
            ),
            "email_unsubscribed": (
                _coerce_bool(email_unsubscribed)
                if incoming_is_newer and email_unsubscribed is not None
                else _coerce_bool(existing.get("email_unsubscribed"))
            ),
            "whatsapp_unsubscribed": (
                _coerce_bool(whatsapp_unsubscribed)
                if incoming_is_newer and whatsapp_unsubscribed is not None
                else _coerce_bool(existing.get("whatsapp_unsubscribed"))
            ),
            "interest_status": merged_interest,
            "last_seen_at": effective_seen_at if incoming_is_newer else existing_last_seen_at,
            "updated_at": _now_iso(),
        }
        try:
            (
                supabase_client.table(MARKETING_CONTACTS_TABLE)
                .update(payload)
                .eq("id", existing.get("id"))
                .execute()
            )
            return True
        except Exception:
            logger.exception(
                "Failed updating marketing contact | client_id=%s | contact_id=%s",
                normalized_client_id,
                existing.get("id"),
            )
            return False

    payload = {
        "client_id": normalized_client_id,
        "name": normalized_name,
        "email": normalized_email,
        "normalized_email": normalized_email,
        "phone": normalized_phone,
        "normalized_phone": normalized_phone,
        "email_opt_in": _coerce_bool(email_opt_in),
        "whatsapp_opt_in": _coerce_bool(whatsapp_opt_in),
        "email_unsubscribed": _coerce_bool(email_unsubscribed),
        "whatsapp_unsubscribed": _coerce_bool(whatsapp_unsubscribed),
        "interest_status": incoming_interest,
        "first_seen_at": effective_seen_at,
        "last_seen_at": effective_seen_at,
        "updated_at": _now_iso(),
    }
    try:
        supabase_client.table(MARKETING_CONTACTS_TABLE).insert(payload).execute()
        return True
    except Exception:
        logger.exception(
            "Failed inserting marketing contact | client_id=%s | email=%s | phone=%s",
            normalized_client_id,
            normalized_email,
            normalized_phone,
        )
        return False
