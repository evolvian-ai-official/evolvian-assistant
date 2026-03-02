from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from collections.abc import Iterable

from api.config.config import supabase

logger = logging.getLogger(__name__)


def _normalize_email(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def _normalize_phone(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned


def _resolve_public_marketing_client_id() -> Optional[str]:
    direct_client_id = str(os.getenv("EVOLVIAN_PUBLIC_MARKETING_CLIENT_ID") or "").strip()
    if direct_client_id:
        return direct_client_id

    public_client_id = str(os.getenv("EVOLVIAN_PUBLIC_MARKETING_PUBLIC_CLIENT_ID") or "").strip()
    if not public_client_id:
        return None

    try:
        res = (
            supabase
            .table("clients")
            .select("id")
            .eq("public_client_id", public_client_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        resolved = str(row.get("id") or "").strip()
        return resolved or None
    except Exception:
        logger.warning(
            "⚠️ Failed resolving public marketing client_id from public_client_id=%s",
            public_client_id,
        )
        return None


def record_marketing_consent(
    *,
    source: str,
    client_id: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    accepted_terms: bool = False,
    accepted_email_marketing: bool = False,
    consent_at: Optional[datetime] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    """
    Canonical marketing consent writer.
    Stores marketing opt-in snapshots into widget_consents so outbound policy
    evaluates every lead source consistently.
    """
    normalized_email = _normalize_email(email)
    normalized_phone = _normalize_phone(phone)
    effective_client_id = str(client_id or "").strip() or _resolve_public_marketing_client_id()

    if not accepted_email_marketing:
        return {"success": False, "skipped": True, "reason": "marketing_not_accepted"}
    if not accepted_terms:
        return {"success": False, "skipped": True, "reason": "terms_not_accepted"}
    if not normalized_email and not normalized_phone:
        return {"success": False, "skipped": True, "reason": "missing_contact_identifier"}
    if not effective_client_id:
        return {"success": False, "skipped": True, "reason": "client_id_unresolved"}

    consent_dt = consent_at or datetime.now(timezone.utc)
    if consent_dt.tzinfo is None:
        consent_dt = consent_dt.replace(tzinfo=timezone.utc)
    else:
        consent_dt = consent_dt.astimezone(timezone.utc)

    payload = {
        "client_id": effective_client_id,
        "email": normalized_email,
        "phone": normalized_phone,
        "accepted_terms": True,
        "accepted_email_marketing": True,
        "consent_at": consent_dt.isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }
    try:
        res = supabase.table("widget_consents").insert(payload).execute()
        row = (res.data or [None])[0] or {}
        return {
            "success": True,
            "skipped": False,
            "consent_token": row.get("id"),
            "client_id": effective_client_id,
        }
    except Exception as error:
        logger.warning(
            "⚠️ Failed recording marketing consent snapshot | source=%s | client_id=%s | email=%s | phone=%s | error=%s",
            source,
            effective_client_id,
            normalized_email,
            normalized_phone,
            error,
        )
        return {"success": False, "skipped": False, "reason": "insert_failed"}


def _parse_iso_utc(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _consent_is_fresh(
    row: dict[str, Any] | None,
    *,
    renewal_days: int,
    now: datetime,
) -> bool:
    if not row:
        return False
    if not bool((row or {}).get("accepted_terms")):
        return False
    if not bool((row or {}).get("accepted_email_marketing")):
        return False
    consent_at = _parse_iso_utc((row or {}).get("consent_at"))
    if not consent_at:
        return False
    expires_at = consent_at.timestamp() + float(max(1, renewal_days) * 86400)
    return now.timestamp() <= expires_at


def backfill_default_marketing_consents_for_contacts(
    *,
    client_id: str,
    contacts: Iterable[dict[str, Any]],
    source: str = "clients_auto_backfill",
) -> dict[str, int]:
    """
    Ensures every provided contact has a fresh marketing consent snapshot.
    Used for "client" contacts that should be selectable for campaigns by default.
    """
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return {"checked": 0, "inserted": 0, "skipped": 0}

    try:
        settings = (
            supabase
            .table("client_settings")
            .select("consent_renewal_days")
            .eq("client_id", normalized_client_id)
            .limit(1)
            .execute()
        ).data or [{}]
        renewal_days = int((settings[0] or {}).get("consent_renewal_days") or 90)
    except Exception:
        renewal_days = 90
    renewal_days = max(1, min(renewal_days, 3650))

    try:
        existing_rows = (
            supabase
            .table("widget_consents")
            .select("email,phone,accepted_terms,accepted_email_marketing,consent_at")
            .eq("client_id", normalized_client_id)
            .order("consent_at", desc=True)
            .limit(5000)
            .execute()
        ).data or []
    except Exception:
        existing_rows = []

    by_exact: dict[tuple[str, str], dict[str, Any]] = {}
    by_email: dict[str, dict[str, Any]] = {}
    by_phone: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        email = _normalize_email((row or {}).get("email")) or ""
        phone = _normalize_phone((row or {}).get("phone")) or ""
        if email and phone:
            by_exact.setdefault((email, phone), row or {})
        if email:
            by_email.setdefault(email, row or {})
        if phone:
            by_phone.setdefault(phone, row or {})

    now = datetime.now(timezone.utc)
    checked = 0
    inserted = 0
    skipped = 0
    seen_keys: set[tuple[str, str]] = set()

    for contact in contacts:
        email = _normalize_email((contact or {}).get("email")) or ""
        phone = _normalize_phone((contact or {}).get("phone")) or ""
        if not email and not phone:
            continue
        dedupe_key = (email, phone)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        checked += 1

        existing = None
        if email and phone:
            existing = by_exact.get((email, phone)) or by_email.get(email) or by_phone.get(phone)
        elif email:
            existing = by_email.get(email)
        elif phone:
            existing = by_phone.get(phone)

        if _consent_is_fresh(existing, renewal_days=renewal_days, now=now):
            skipped += 1
            continue

        result = record_marketing_consent(
            source=source,
            client_id=normalized_client_id,
            email=email or None,
            phone=phone or None,
            accepted_terms=True,
            accepted_email_marketing=True,
            consent_at=now,
            ip_address="system_auto_backfill_clients",
            user_agent="system_auto_backfill_clients",
        )
        if result.get("success"):
            inserted += 1
        else:
            skipped += 1

    return {"checked": checked, "inserted": inserted, "skipped": skipped}
