from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from api.config.config import supabase

logger = logging.getLogger(__name__)

TERMINAL_DSAR_STATUSES = {"withdrawn", "denied"}


@dataclass
class ConsentSnapshot:
    consent_id: str | None
    consent_at: datetime | None
    accepted_terms: bool
    accepted_email_marketing: bool
    email_present: bool
    phone_present: bool


@dataclass
class PolicySettings:
    require_email_consent: bool
    require_phone_consent: bool
    require_terms_consent: bool
    consent_renewal_days: int
    require_reminder_consent: bool
    require_marketing_opt_in: bool
    allow_transactional_without_consent: bool


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_email(value: str | None) -> str | None:
    email = (value or "").strip().lower()
    return email or None


def _normalize_phone(value: str | None) -> str | None:
    phone = (value or "").strip()
    if not phone:
        return None
    return phone.replace(" ", "").replace("-", "")


def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_policy_settings(client_id: str) -> PolicySettings:
    try:
        res = (
            supabase.table("client_settings")
            .select(
                "require_email_consent,require_phone_consent,require_terms_consent,consent_renewal_days"
            )
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [{}])[0]
    except Exception:
        row = {}

    renewal_days = int(row.get("consent_renewal_days") or 90)
    renewal_days = max(1, min(renewal_days, 3650))

    return PolicySettings(
        require_email_consent=bool(row.get("require_email_consent", False)),
        require_phone_consent=bool(row.get("require_phone_consent", False)),
        require_terms_consent=bool(row.get("require_terms_consent", False)),
        consent_renewal_days=renewal_days,
        require_reminder_consent=_env_flag("EVOLVIAN_REQUIRE_CONSENT_FOR_REMINDERS", True),
        require_marketing_opt_in=_env_flag("EVOLVIAN_REQUIRE_MARKETING_OPT_IN", True),
        allow_transactional_without_consent=_env_flag(
            "EVOLVIAN_ALLOW_TRANSACTIONAL_WITHOUT_CONSENT", True
        ),
    )


def _load_latest_contact_consent(
    *,
    client_id: str,
    email: str | None,
    phone: str | None,
) -> ConsentSnapshot:
    if not email and not phone:
        return ConsentSnapshot(
            consent_id=None,
            consent_at=None,
            accepted_terms=False,
            accepted_email_marketing=False,
            email_present=False,
            phone_present=False,
        )

    query = (
        supabase.table("widget_consents")
        .select("id,consent_at,email,phone,accepted_terms,accepted_email_marketing")
        .eq("client_id", client_id)
        .order("consent_at", desc=True)
        .limit(1)
    )
    if email:
        query = query.eq("email", email)
    if phone:
        query = query.eq("phone", phone)

    try:
        row = (query.execute().data or [None])[0] or {}
    except Exception:
        row = {}

    consent_at = _parse_iso(row.get("consent_at"))
    return ConsentSnapshot(
        consent_id=str(row.get("id")) if row.get("id") else None,
        consent_at=consent_at,
        accepted_terms=bool(row.get("accepted_terms")),
        accepted_email_marketing=bool(row.get("accepted_email_marketing")),
        email_present=bool((row.get("email") or "").strip()),
        phone_present=bool((row.get("phone") or "").strip()),
    )


def _load_marketing_opt_out(email: str | None) -> dict[str, Any] | None:
    if not email:
        return None
    try:
        res = (
            supabase.table("public_privacy_requests")
            .select("id,request_type,status,created_at")
            .eq("email", email)
            .eq("request_type", "marketing_opt_out")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        if not row:
            return None
        status = str(row.get("status") or "pending").strip().lower()
        if status in TERMINAL_DSAR_STATUSES:
            return None
        return {
            "id": row.get("id"),
            "status": status,
            "created_at": row.get("created_at"),
        }
    except Exception:
        return None


def evaluate_policy_decision(
    *,
    channel: str,
    purpose: str,
    settings: PolicySettings,
    consent: ConsentSnapshot,
    opt_out: dict[str, Any] | None,
    recipient_email: str | None,
    recipient_phone: str | None,
    now: datetime,
) -> tuple[bool, str | None, datetime | None]:
    normalized_channel = (channel or "").strip().lower()
    normalized_purpose = (purpose or "").strip().lower()
    if normalized_channel not in {"email", "whatsapp"}:
        return False, "unsupported_channel", None
    if normalized_purpose not in {"marketing", "reminder", "transactional"}:
        return False, "unsupported_purpose", None

    requires_email = normalized_channel == "email"
    requires_phone = normalized_channel == "whatsapp"

    if requires_email and not recipient_email:
        return False, "missing_recipient_email", None
    if requires_phone and not recipient_phone:
        return False, "missing_recipient_phone", None

    expires_at = None
    if consent.consent_at:
        expires_at = consent.consent_at + timedelta(days=settings.consent_renewal_days)

    consent_fresh = bool(consent.consent_at and expires_at and now <= expires_at)
    terms_ok = consent.accepted_terms
    email_optin_ok = consent.accepted_email_marketing

    if normalized_purpose == "marketing":
        if opt_out:
            return False, "marketing_opt_out_request_exists", expires_at
        if settings.require_marketing_opt_in:
            if not consent_fresh:
                return False, "missing_or_expired_marketing_consent", expires_at
            if requires_email and not email_optin_ok:
                return False, "email_marketing_not_opted_in", expires_at
            if requires_email and not consent.email_present:
                return False, "missing_email_in_consent_record", expires_at
            if requires_phone and not consent.phone_present:
                return False, "missing_phone_in_consent_record", expires_at
            if not terms_ok:
                return False, "missing_terms_acceptance_for_marketing", expires_at
        return True, None, expires_at

    if normalized_purpose == "reminder":
        if settings.require_reminder_consent:
            if not consent_fresh:
                return False, "missing_or_expired_reminder_consent", expires_at
            if requires_email and not consent.email_present:
                return False, "missing_email_in_consent_record", expires_at
            if requires_phone and not consent.phone_present:
                return False, "missing_phone_in_consent_record", expires_at
            if not terms_ok:
                return False, "missing_terms_acceptance_for_reminder", expires_at
        elif settings.require_terms_consent and not terms_ok:
            return False, "missing_terms_acceptance_for_reminder", expires_at
        return True, None, expires_at

    # transactional
    if settings.allow_transactional_without_consent:
        return True, None, expires_at

    if settings.require_email_consent and requires_email:
        if not consent_fresh or not consent.email_present:
            return False, "missing_or_expired_email_consent", expires_at
    if settings.require_phone_consent and requires_phone:
        if not consent_fresh or not consent.phone_present:
            return False, "missing_or_expired_phone_consent", expires_at
    if settings.require_terms_consent and not terms_ok:
        return False, "missing_terms_acceptance_for_transactional", expires_at

    return True, None, expires_at


def evaluate_outbound_policy(
    *,
    client_id: str,
    channel: str,
    purpose: str,
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    source: str = "unknown",
    source_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    email = _normalize_email(recipient_email)
    phone = _normalize_phone(recipient_phone)

    settings = _load_policy_settings(client_id)
    consent = _load_latest_contact_consent(client_id=client_id, email=email, phone=phone)
    opt_out = _load_marketing_opt_out(email)

    allowed, reason, expires_at = evaluate_policy_decision(
        channel=channel,
        purpose=purpose,
        settings=settings,
        consent=consent,
        opt_out=opt_out,
        recipient_email=email,
        recipient_phone=phone,
        now=now,
    )

    return {
        "proof_id": f"proof_{uuid.uuid4().hex[:12]}",
        "allowed": allowed,
        "reason": reason,
        "channel": channel,
        "purpose": purpose,
        "recipient_email": email,
        "recipient_phone": phone,
        "consent_id": consent.consent_id,
        "consent_at": consent.consent_at.isoformat() if consent.consent_at else None,
        "consent_expires_at": expires_at.isoformat() if expires_at else None,
        "marketing_opt_out_request_id": (opt_out or {}).get("id"),
        "marketing_opt_out_status": (opt_out or {}).get("status"),
        "source": source,
        "source_id": source_id,
        "evaluated_at": now.isoformat(),
        "rules": {
            "require_email_consent": settings.require_email_consent,
            "require_phone_consent": settings.require_phone_consent,
            "require_terms_consent": settings.require_terms_consent,
            "consent_renewal_days": settings.consent_renewal_days,
            "require_reminder_consent": settings.require_reminder_consent,
            "require_marketing_opt_in": settings.require_marketing_opt_in,
            "allow_transactional_without_consent": settings.allow_transactional_without_consent,
        },
    }


def log_outbound_policy_event(
    *,
    client_id: str,
    policy_result: dict[str, Any],
    stage: str,
    send_status: str,
    provider_message_id: str | None = None,
    send_error: str | None = None,
) -> None:
    try:
        proof_id = str(policy_result.get("proof_id") or "")
        channel = str(policy_result.get("channel") or "unknown")
        purpose = str(policy_result.get("purpose") or "unknown")
        content = (
            f"Outbound policy {stage}: channel={channel}, purpose={purpose}, "
            f"allowed={policy_result.get('allowed')}, status={send_status}"
        )
        metadata = {
            "compliance_event": "outbound_policy",
            "proof_id": proof_id,
            "stage": stage,
            "send_status": send_status,
            "provider_message_id": provider_message_id,
            "send_error": send_error,
            "policy": policy_result,
        }
        supabase.table("history").insert(
            {
                "client_id": client_id,
                "session_id": proof_id or None,
                "role": "system",
                "content": content,
                "channel": channel,
                "source_type": "compliance_outbound_policy",
                "provider": "internal",
                "source_id": policy_result.get("source_id"),
                "status": send_status,
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as error:
        logger.warning("⚠️ Could not persist outbound policy audit event: %s", error)

