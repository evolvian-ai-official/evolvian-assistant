from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict
import asyncio
import uuid
import logging
import json
import os
import re
import requests
from babel.dates import format_datetime

from api.config.config import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)
from api.modules.calendar.send_confirmation_email import send_confirmation_email
from api.authz import authorize_client_request
from api.internal_auth import has_valid_internal_token
from api.appointments.cancel_link_tokens import build_cancel_link, generate_cancel_token
from api.appointments.cancellation_notifications import (
    send_appointment_cancellation_email_notification,
    send_appointment_cancellation_notification,
)
from api.appointments.template_language_resolution import (
    get_client_default_language_preferences,
    normalize_language_preferences,
    resolve_locale_for_rendering,
    resolve_template_for_appointment,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TIMEZONE_ALIASES = {
    "america new york time": "America/New_York",
    "america/newyork": "America/New_York",
    "new york": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "america mexico city": "America/Mexico_City",
    "mexico city": "America/Mexico_City",
    "cst": "America/Mexico_City",
}

WEEKDAY_MAP = {
    "mon": 0, "monday": 0, "lun": 0, "lunes": 0,
    "tue": 1, "tuesday": 1, "mar": 1, "martes": 1,
    "wed": 2, "wednesday": 2, "mie": 2, "miercoles": 2, "miércoles": 2,
    "thu": 3, "thursday": 3, "jue": 3, "jueves": 3,
    "fri": 4, "friday": 4, "vie": 4, "viernes": 4,
    "sat": 5, "saturday": 5, "sab": 5, "sabado": 5, "sábado": 5,
    "sun": 6, "sunday": 6, "dom": 6, "domingo": 6,
}

LANGUAGE_TO_LOCALE = {
    "es": "es_MX",
    "en": "en_US",
    "pt": "pt_BR",
}

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
E164_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def is_calendar_active_for_client(client_id: str) -> bool:
    """
    Master flag for appointments. If inactive, no new appointments can be created
    from any channel (manual, chat, widget, whatsapp).
    """
    try:
        res = (
            supabase
            .table("calendar_settings")
            .select("calendar_status")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        status = (res.data or [{}])[0].get("calendar_status")
        return status == "active"
    except Exception as e:
        logger.error(f"❌ Failed to check calendar_status for {client_id}: {e}")
        return False


def _normalize_selected_days(raw_days) -> set[int]:
    if not raw_days:
        return {0, 1, 2, 3, 4}
    if isinstance(raw_days, str):
        raw_days = [d.strip() for d in raw_days.split(",") if d.strip()]

    out: set[int] = set()
    for item in (raw_days or []):
        if isinstance(item, int):
            if 0 <= item <= 6:
                out.add(item)
            continue
        key = str(item).strip().lower()
        key = key.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if key in WEEKDAY_MAP:
            out.add(WEEKDAY_MAP[key])
    return out or {0, 1, 2, 3, 4}


def _load_calendar_rules(client_id: str) -> dict:
    defaults = {
        "selected_days": {0, 1, 2, 3, 4},
        "start_time": "09:00",
        "end_time": "18:00",
        "slot_duration_minutes": 30,
        "buffer_minutes": 15,
        "min_notice_hours": 0,
        "allow_same_day": True,
        "max_days_ahead": 365,
    }
    try:
        res = (
            supabase
            .table("calendar_settings")
            .select(
                "selected_days, start_time, end_time, slot_duration_minutes, "
                "buffer_minutes, min_notice_hours, allow_same_day, max_days_ahead"
            )
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        data = (res.data or [{}])[0]
    except Exception:
        data = {}

    def _value_or_default(key: str):
        val = data.get(key)
        return defaults[key] if val is None else val

    return {
        "selected_days": _normalize_selected_days(data.get("selected_days") or defaults["selected_days"]),
        "start_time": _value_or_default("start_time"),
        "end_time": _value_or_default("end_time"),
        "slot_duration_minutes": max(5, min(int(_value_or_default("slot_duration_minutes")), 240)),
        "buffer_minutes": max(0, min(int(_value_or_default("buffer_minutes")), 240)),
        "min_notice_hours": max(0, min(int(_value_or_default("min_notice_hours")), 720)),
        "allow_same_day": bool(data.get("allow_same_day", defaults["allow_same_day"])),
        "max_days_ahead": max(1, min(int(_value_or_default("max_days_ahead")), 365)),
    }


def _parse_expires_at(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _refresh_google_access_token(client_id: str, refresh_token: str) -> str:
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not google_client_id or not google_client_secret:
        raise RuntimeError("Missing Google OAuth credentials")

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": google_client_id,
            "client_secret": google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token refresh failed with status {response.status_code}")

    payload = response.json()
    new_token = payload.get("access_token")
    if not new_token:
        raise RuntimeError("Token refresh response missing access_token")

    expires_in = int(payload.get("expires_in") or 3600)
    expires_at = (datetime.utcnow() + timedelta(seconds=max(60, expires_in - 30))).isoformat()
    supabase.table("calendar_integrations").update(
        {"access_token": new_token, "expires_at": expires_at}
    ).eq("client_id", client_id).eq("is_active", True).execute()
    return new_token


def _get_active_google_integration(client_id: str) -> Optional[dict]:
    res = (
        supabase
        .table("calendar_integrations")
        .select("access_token, refresh_token, calendar_id, expires_at")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def _resolve_google_access_token(client_id: str, integration: dict) -> str:
    access_token = integration.get("access_token")
    refresh_token = integration.get("refresh_token")
    expires_at = _parse_expires_at(integration.get("expires_at"))
    refresh_threshold = datetime.now(timezone.utc) + timedelta(minutes=1)

    if access_token and expires_at and expires_at <= refresh_threshold and refresh_token:
        access_token = _refresh_google_access_token(client_id, refresh_token)
    elif not access_token and refresh_token:
        access_token = _refresh_google_access_token(client_id, refresh_token)

    if not access_token:
        raise RuntimeError("Missing Google access token")
    return access_token


def _is_google_slot_busy(client_id: str, start_utc: datetime, end_utc: datetime) -> bool:
    integration = _get_active_google_integration(client_id)
    if not integration:
        return False

    calendar_id = integration.get("calendar_id") or "primary"
    access_token = _resolve_google_access_token(client_id, integration)

    def _freebusy_request(token: str):
        return requests.post(
            GOOGLE_FREEBUSY_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "timeMin": start_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "timeMax": end_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "timeZone": "UTC",
                "items": [{"id": calendar_id}],
            },
            timeout=10,
        )

    response = _freebusy_request(access_token)
    if response.status_code == 401 and integration.get("refresh_token"):
        access_token = _refresh_google_access_token(client_id, integration["refresh_token"])
        response = _freebusy_request(access_token)

    if response.status_code >= 400:
        raise RuntimeError(f"Google freeBusy failed with status {response.status_code}")

    payload = response.json()
    calendars = payload.get("calendars") or {}
    calendar_data = calendars.get(calendar_id)
    if calendar_data is None and len(calendars) == 1:
        calendar_data = next(iter(calendars.values()))
    busy_ranges = (calendar_data or {}).get("busy") or []
    return bool(busy_ranges)


def _get_google_busy_ranges(client_id: str, start_utc: datetime, end_utc: datetime) -> list[dict]:
    integration = _get_active_google_integration(client_id)
    if not integration:
        return []

    calendar_id = integration.get("calendar_id") or "primary"
    access_token = _resolve_google_access_token(client_id, integration)

    def _freebusy_request(token: str):
        return requests.post(
            GOOGLE_FREEBUSY_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "timeMin": start_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "timeMax": end_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "timeZone": "UTC",
                "items": [{"id": calendar_id}],
            },
            timeout=10,
        )

    response = _freebusy_request(access_token)
    if response.status_code == 401 and integration.get("refresh_token"):
        access_token = _refresh_google_access_token(client_id, integration["refresh_token"])
        response = _freebusy_request(access_token)

    if response.status_code >= 400:
        raise RuntimeError(f"Google freeBusy failed with status {response.status_code}")

    payload = response.json()
    calendars = payload.get("calendars") or {}
    calendar_data = calendars.get(calendar_id)
    if calendar_data is None and len(calendars) == 1:
        calendar_data = next(iter(calendars.values()))
    raw_busy = (calendar_data or {}).get("busy") or []

    normalized = []
    for item in raw_busy:
        raw_start = item.get("start")
        raw_end = item.get("end")
        if not raw_start or not raw_end:
            continue
        try:
            busy_start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
            if busy_start.tzinfo is None:
                busy_start = busy_start.replace(tzinfo=timezone.utc)
            if busy_end.tzinfo is None:
                busy_end = busy_end.replace(tzinfo=timezone.utc)
            normalized.append(
                {
                    "start": busy_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "end": busy_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
        except Exception:
            continue

    normalized.sort(key=lambda x: x["start"])
    return normalized


# =====================================================
# Timezone helper (solo agregado, no cambia lógica)
# =====================================================
def get_client_timezone(client_id: str) -> ZoneInfo:
    try:
        res = (
            supabase
            .table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if not res.data:
            return ZoneInfo("UTC")

        tz_raw = (res.data[0].get("timezone") or "UTC").strip()
        tz_key = tz_raw.lower().replace("_", " ").replace("/", " ").strip()
        tz_str = TIMEZONE_ALIASES.get(tz_key, tz_raw)

        # Try common normalization: "America New York Time" -> "America/New_York"
        if " " in tz_str and "/" not in tz_str:
            compact = "_".join([part for part in tz_str.replace("time", "").split() if part])
            if compact.lower().startswith("america_"):
                tz_str = compact.replace("America_", "America/")

        return ZoneInfo(tz_str)

    except Exception as e:
        logger.error(f"❌ Failed to get timezone: {e}")
        return ZoneInfo("UTC")


def get_client_company_name(client_id: str) -> str:
    default_name = "su empresa"

    if not client_id:
        return default_name

    try:
        profile_res = (
            supabase
            .table("client_profile")
            .select("company_name")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        if profile_res.data:
            company_name = (profile_res.data[0].get("company_name") or "").strip()
            if company_name:
                return company_name
    except Exception as e:
        logger.warning("⚠️ Failed loading client_profile.company_name | client_id=%s | error=%s", client_id, e)

    try:
        client_res = (
            supabase
            .table("clients")
            .select("name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        if client_res.data:
            client_name = (client_res.data[0].get("name") or "").strip()
            if client_name:
                return client_name
    except Exception as e:
        logger.warning("⚠️ Failed loading clients.name | client_id=%s | error=%s", client_id, e)

    return default_name


def get_client_locale(client_id: str) -> str:
    if not client_id:
        return "es_MX"
    try:
        settings_res = (
            supabase
            .table("client_settings")
            .select("language")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        language = ((settings_res.data or [{}])[0].get("language") or "es").lower()
        return LANGUAGE_TO_LOCALE.get(language, "es_MX")
    except Exception as e:
        logger.warning("⚠️ Failed loading client locale | client_id=%s | error=%s", client_id, e)
        return "es_MX"


def render_email_template_text(template_text: Optional[str], replacements: Dict[str, str]) -> Optional[str]:
    if not template_text:
        return template_text

    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value or "")
    return rendered


def build_confirmation_parameters(
    expected_params: int,
    *,
    user_name: str,
    company_name: str,
    formatted_date: str,
    appointment_type: str,
) -> list[str]:
    safe_user = (user_name or "Cliente").strip() or "Cliente"
    safe_company = (company_name or "su empresa").strip() or "su empresa"
    safe_date = (formatted_date or "Cita programada").strip() or "Cita programada"
    safe_type = (appointment_type or "Cita").strip() or "Cita"

    if expected_params <= 0:
        return []
    if expected_params == 1:
        return [safe_date]
    if expected_params == 2:
        return [safe_user, safe_date]
    if expected_params == 3:
        return [safe_user, safe_company, safe_date]

    base = [safe_user, safe_company, safe_date, safe_type]
    if expected_params <= len(base):
        return base[:expected_params]

    return base + ["Información de cita"] * (expected_params - len(base))


# =========================
# Payload
# =========================
class CreateAppointmentPayload(BaseModel):
    client_id: uuid.UUID
    session_id: uuid.UUID
    scheduled_time: datetime
    user_name: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    appointment_type: Optional[str] = "general"
    channel: Optional[str] = "chat"
    send_reminders: bool = False
    reminders: Optional[Dict[str, Optional[str]]] = None
    replace_existing: bool = False
    recipient_language: Optional[str] = None
    recipient_locale: Optional[str] = None
    consent_accepted_terms: Optional[bool] = None
    consent_accepted_email_marketing: Optional[bool] = None
    consent_captured_at: Optional[datetime] = None
    consent_user_agent: Optional[str] = None


def _resolve_payload_recipient_language(payload: CreateAppointmentPayload) -> tuple[str, str]:
    default_family, _ = get_client_default_language_preferences(str(payload.client_id))
    return normalize_language_preferences(
        language_family=payload.recipient_language,
        locale_code=payload.recipient_locale,
        fallback_language=default_family,
    )


def _normalize_phone_e164_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"
    if not E164_PHONE_RE.fullmatch(raw):
        return None
    return raw


def _capture_inline_contact_consent(payload: CreateAppointmentPayload) -> str | None:
    """
    Persist consent provided during appointment creation (non-widget flows).
    Returns consent record id when created.
    """
    if payload.consent_accepted_terms is None and payload.consent_accepted_email_marketing is None:
        return None

    email_value = (str(payload.user_email).strip().lower() if payload.user_email else None) or None
    phone_value = (payload.user_phone or "").strip() or None
    if not email_value and not phone_value:
        logger.warning(
            "⚠️ Inline consent skipped (missing subject) | client_id=%s",
            str(payload.client_id),
        )
        return None

    captured_at = payload.consent_captured_at
    if captured_at is None:
        captured_at = datetime.now(timezone.utc)
    elif captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    else:
        captured_at = captured_at.astimezone(timezone.utc)

    record = {
        "client_id": str(payload.client_id),
        "email": email_value,
        "phone": phone_value,
        "accepted_terms": bool(payload.consent_accepted_terms),
        "accepted_email_marketing": bool(payload.consent_accepted_email_marketing),
        "consent_at": captured_at.isoformat(),
        "ip_address": None,
        "user_agent": (payload.consent_user_agent or "appointments_inline").strip()[:500],
    }
    result = supabase.table("widget_consents").insert(record).execute()
    consent_row = result.data[0] if result and result.data else {}
    consent_id = consent_row.get("id")
    logger.info(
        "🧾 Inline consent captured | client_id=%s | consent_id=%s | email=%s | phone=%s",
        str(payload.client_id),
        consent_id or "-",
        email_value or "-",
        phone_value or "-",
    )
    return str(consent_id) if consent_id else None


# =========================
# Internal helper
# =========================
async def send_appointment_confirmation(appointment: dict) -> None:
    client_id = appointment.get("client_id")
    phone = appointment.get("user_phone")

    if not client_id or not phone:
        logger.warning(
            "⚠️ Appointment confirmation skipped — missing client_id or phone"
        )
        return

    # 1️⃣ Resolve active confirmation template by recipient language
    template = resolve_template_for_appointment(
        client_id=str(client_id),
        channel="whatsapp",
        template_type="appointment_confirmation",
        appointment=appointment,
    )
    if not template:
        logger.info("ℹ️ No active appointment_confirmation template found")
        return

    meta_template_id = template.get("meta_template_id")
    meta = template.get("_resolved_meta")
    if not meta and meta_template_id:
        meta_res = (
            supabase
            .table("meta_approved_templates")
            .select("template_name, language, parameter_count")
            .eq("id", meta_template_id)
            .eq("is_active", True)
            .single()
            .execute()
        )
        meta = meta_res.data

    if not meta:
        logger.warning(
            "⚠️ Meta template metadata not found | meta_template_id=%s",
            meta_template_id,
        )
        return

    template_name = meta.get("template_name")
    _, language_code = resolve_locale_for_rendering(
        client_id=str(client_id),
        appointment=appointment,
        template_row=template,
        meta_row=meta,
    )
    expected_params = int(meta.get("parameter_count") or 2)

    if not template_name:
        logger.warning("⚠️ Meta template missing template_name")
        return

    logger.info(f"📨 Using template: {template_name}")

    # 3️⃣ Format date using client timezone
    try:
        raw_time = appointment.get("scheduled_time")
        if not raw_time:
            raise Exception("Missing scheduled_time")

        scheduled_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))

        # 🔥 SOLO agregado: usar timezone del cliente
        client_tz = get_client_timezone(str(client_id))
        scheduled_local = scheduled_utc.astimezone(client_tz)

        formatted_date = format_datetime(
            scheduled_local,
            "EEEE, MMMM dd yyyy, hh:mm a"
            if str(language_code).lower().startswith("en")
            else "EEEE dd 'de' MMMM yyyy, hh:mm a",
            locale=language_code,
        )

    except Exception as e:
        logger.error(f"❌ Failed formatting date with Babel: {e}")
        formatted_date = appointment.get("scheduled_time")

    parameters = build_confirmation_parameters(
        expected_params,
        user_name=appointment.get("user_name") or "Cliente",
        company_name=get_client_company_name(str(client_id)),
        formatted_date=formatted_date or "Cita programada",
        appointment_type=appointment.get("appointment_type") or "",
    )

    # 4️⃣ Send template (NO cambiado)
    result = await send_whatsapp_template_for_client(
        client_id=client_id,
        to_number=phone,
        template_name=template_name,
        language_code=language_code,
        parameters=parameters,
        purpose="transactional",
        recipient_email=appointment.get("user_email"),
        policy_source="appointments_confirmation",
        policy_source_id=str(appointment.get("id") or ""),
    )

    if not result["success"]:
        logger.error(
            "❌ Appointment confirmation failed | client_id=%s | error=%s",
            client_id,
            result.get("error"),
        )
    else:
        logger.info(
            "✅ Appointment confirmation sent | message_id=%s",
            result.get("meta_message_id"),
        )


def send_appointment_email_confirmation(appointment: dict) -> None:
    """
    Sends an immediate email confirmation using Resend when user_email exists.
    Independent from WhatsApp template flow.
    """
    email = appointment.get("user_email")
    raw_time = appointment.get("scheduled_time")
    if not email or not raw_time:
        logger.info("ℹ️ Email confirmation skipped — missing user_email or scheduled_time")
        return

    try:
        scheduled_utc = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        client_id = str(appointment.get("client_id"))
        client_tz = get_client_timezone(client_id) if client_id else ZoneInfo("UTC")
        scheduled_local = scheduled_utc.astimezone(client_tz)
        locale_code = get_client_locale(client_id) if client_id else "es_MX"

        date_str = scheduled_local.strftime("%Y-%m-%d")
        hour_str = scheduled_local.strftime("%H:%M")

        # Use active email appointment_confirmation template if available.
        subject = None
        html_body = None
        cancel_link_for_email = None
        if client_id:
            template = resolve_template_for_appointment(
                client_id=client_id,
                channel="email",
                template_type="appointment_confirmation",
                appointment=appointment,
                require_body=True,
            )
            if template:
                _, locale_code = resolve_locale_for_rendering(
                    client_id=client_id,
                    appointment=appointment,
                    template_row=template,
                )
                company_name = get_client_company_name(client_id)
                cancel_link = ""
                try:
                    token = generate_cancel_token(
                        client_id=client_id,
                        appointment_id=str(appointment.get("id") or ""),
                        recipient_email=email,
                    )
                    if token:
                        cancel_link = build_cancel_link(token)
                except Exception:
                    cancel_link = ""
                cancel_link_for_email = cancel_link or None
                cancel_button_html = (
                    f"<a href=\"{cancel_link}\" "
                    "style=\"display:inline-block;padding:10px 16px;background:#f8fafc;color:#334155;"
                    "text-decoration:none;border:1px solid #d1d5db;border-radius:8px;font-weight:600;\">Cancelar cita</a>"
                    if cancel_link else ""
                )

                scheduled_label = format_datetime(
                    scheduled_local,
                    "EEEE, MMMM dd yyyy, hh:mm a"
                    if str(locale_code).lower().startswith("en")
                    else "EEEE dd 'de' MMMM yyyy, hh:mm a",
                    locale=locale_code,
                )
                appointment_date = format_datetime(
                    scheduled_local,
                    "EEEE, MMMM dd yyyy"
                    if str(locale_code).lower().startswith("en")
                    else "EEEE dd 'de' MMMM yyyy",
                    locale=locale_code,
                )
                appointment_time = format_datetime(
                    scheduled_local,
                    "hh:mm a",
                    locale=locale_code,
                )
                today_date = format_datetime(
                    datetime.now(client_tz),
                    "EEEE, MMMM dd yyyy"
                    if str(locale_code).lower().startswith("en")
                    else "EEEE dd 'de' MMMM yyyy",
                    locale=locale_code,
                )

                replacements = {
                    "company_name": company_name or "",
                    "user_name": appointment.get("user_name", "") or "Cliente",
                    "user_email": appointment.get("user_email", "") or "",
                    "appointment_type": appointment.get("appointment_type", "") or "",
                    "scheduled_time": scheduled_label,
                    "appointment_date": appointment_date,
                    "appointment_time": appointment_time,
                    "current_date": today_date,
                    "cancel_appointment_link": cancel_link,
                    "cancel_appointment_button": cancel_button_html,
                }

                html_body = render_email_template_text(template.get("body", ""), replacements)
                raw_subject = (template.get("label") or "").strip() or None
                rendered_subject = render_email_template_text(raw_subject, replacements)
                subject = (rendered_subject or "").replace("\r", " ").replace("\n", " ").strip() or None

        email_sent = send_confirmation_email(
            email,
            date_str,
            hour_str,
            html_body=html_body,
            subject=subject,
            client_id=client_id,
            user_name=appointment.get("user_name"),
            appointment_type=appointment.get("appointment_type"),
            purpose="transactional",
            cancel_link=cancel_link_for_email,
        )
        if email_sent:
            logger.info("✅ Appointment email confirmation sent to %s", email)
        else:
            logger.warning("⚠️ Appointment email confirmation skipped/blocked for %s", email)
    except Exception as e:
        logger.error("❌ Failed sending appointment email confirmation: %s", e)


# =========================
# Google busy ranges (UI)
# =========================
@router.get("/calendar/google_busy_slots", tags=["Appointments"])
def get_google_busy_slots(
    request: Request,
    client_id: str = Query(...),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        authorize_client_request(request, client_id)

        try:
            start_day = datetime.strptime(from_date, "%Y-%m-%d")
            end_day = datetime.strptime(to_date, "%Y-%m-%d")
        except Exception:
            raise HTTPException(status_code=400, detail="from_date/to_date must be YYYY-MM-DD")

        if end_day < start_day:
            raise HTTPException(status_code=400, detail="to_date must be greater or equal to from_date")

        if (end_day - start_day).days > 366:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 366 days")

        client_tz = get_client_timezone(client_id)
        start_local = start_day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=client_tz)
        end_local = end_day.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=client_tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        busy_ranges = _get_google_busy_ranges(client_id, start_utc, end_utc)
        return JSONResponse(
            content={
                "success": True,
                "busy_ranges": busy_ranges,
                "timezone": getattr(client_tz, "key", str(client_tz)),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Failed to fetch Google busy ranges")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Endpoint
# =========================
async def create_appointment(payload: CreateAppointmentPayload):
    if not is_calendar_active_for_client(str(payload.client_id)):
        return {
            "success": False,
            "calendar_inactive": True,
            "message": "Appointments are currently disabled for this client.",
        }

    # 🔥 SOLO agregado: obtener timezone del cliente
    LOCAL_TZ = get_client_timezone(str(payload.client_id))
    rules = _load_calendar_rules(str(payload.client_id))

    payload.user_name = " ".join(str(payload.user_name or "").strip().split())
    if len(payload.user_name) < 2:
        return {
            "success": False,
            "invalid_time": True,
            "message": "Client name must have at least 2 characters.",
        }

    if payload.user_phone is not None:
        normalized_phone = _normalize_phone_e164_or_none(payload.user_phone)
        if payload.user_phone and not normalized_phone:
            return {
                "success": False,
                "invalid_time": True,
                "message": "Phone must include country code and use international format (e.g. +525512345678).",
            }
        payload.user_phone = normalized_phone

    if payload.user_email is not None:
        payload.user_email = str(payload.user_email).strip().lower() or None

    if payload.scheduled_time.tzinfo is None:
        scheduled_local = payload.scheduled_time.replace(tzinfo=LOCAL_TZ)
    else:
        scheduled_local = payload.scheduled_time.astimezone(LOCAL_TZ)

    # Guardamos siempre en UTC (esto ya lo hacías)
    scheduled_utc = scheduled_local.astimezone(timezone.utc)
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)

    logger.info(
        "🧪 Appointment validation input | client_id=%s | scheduled_local=%s | rules=%s",
        str(payload.client_id),
        scheduled_local.isoformat(),
        {
            "selected_days": sorted(list(rules.get("selected_days", []))),
            "start_time": rules.get("start_time"),
            "end_time": rules.get("end_time"),
            "slot_duration_minutes": rules.get("slot_duration_minutes"),
            "buffer_minutes": rules.get("buffer_minutes"),
            "min_notice_hours": rules.get("min_notice_hours"),
            "max_days_ahead": rules.get("max_days_ahead"),
            "allow_same_day": rules.get("allow_same_day"),
        },
    )

    # =====================================================
    # 🛡️ Reglas base de agenda (aplican a Admin/Widget/Chat/WhatsApp)
    # =====================================================
    if scheduled_utc < now_utc:
        return {
            "success": False,
            "invalid_time": True,
            "message": "Cannot book past times.",
        }

    if scheduled_utc > (now_utc + timedelta(days=365)):
        return {
            "success": False,
            "invalid_time": True,
            "message": "Cannot book beyond one year.",
        }

    # =====================================================
    # 📐 Reglas de Calendar Setup (también para manual)
    # =====================================================
    start_time = rules["start_time"]
    end_time = rules["end_time"]
    slot_duration_min = rules["slot_duration_minutes"]
    buffer_min = rules["buffer_minutes"]
    min_notice_h = rules["min_notice_hours"]
    max_days_ahead = rules["max_days_ahead"]
    allow_same_day = rules["allow_same_day"]
    selected_days = rules["selected_days"]

    try:
        start_h, start_m = [int(v) for v in str(start_time).split(":", 1)]
        end_h, end_m = [int(v) for v in str(end_time).split(":", 1)]
    except Exception:
        start_h, start_m = 9, 0
        end_h, end_m = 18, 0

    if (end_h, end_m) <= (start_h, start_m):
        start_h, start_m = 9, 0
        end_h, end_m = 18, 0

    if scheduled_local.weekday() not in selected_days:
        return {
            "success": False,
            "invalid_time": True,
            "message": "Selected day is not available for booking.",
        }

    day_start = scheduled_local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    day_end = scheduled_local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    slot_delta = timedelta(minutes=slot_duration_min)
    slot_end_local = scheduled_local + slot_delta

    if scheduled_local < day_start or slot_end_local > day_end:
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Selected time is outside working hours ({start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}).",
        }

    if not allow_same_day and scheduled_local.date() == now_local.date():
        return {
            "success": False,
            "invalid_time": True,
            "message": "Same-day bookings are disabled.",
        }

    if scheduled_local < now_local + timedelta(hours=min_notice_h):
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Minimum notice is {min_notice_h} hour(s).",
        }

    if scheduled_local > now_local + timedelta(days=max_days_ahead):
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Bookings are allowed up to {max_days_ahead} day(s) ahead.",
        }

    step_min = max(1, slot_duration_min + buffer_min)
    scheduled_minutes = (scheduled_local.hour * 60) + scheduled_local.minute
    start_minutes = (start_h * 60) + start_m
    minutes_from_start = scheduled_minutes - start_minutes

    valid_start_minutes = set()
    probe = day_start
    step_delta = timedelta(minutes=step_min)
    while probe + slot_delta <= day_end:
        valid_start_minutes.add((probe.hour * 60) + probe.minute)
        probe += step_delta

    if minutes_from_start < 0 or scheduled_minutes not in valid_start_minutes:
        logger.warning(
            "⚠️ Interval mismatch | scheduled_minutes=%s | start_minutes=%s | minutes_from_start=%s | step=%s | slot=%s | buffer=%s | valid_starts=%s",
            scheduled_minutes,
            start_minutes,
            minutes_from_start,
            step_min,
            slot_duration_min,
            buffer_min,
            sorted(valid_start_minutes),
        )
        return {
            "success": False,
            "invalid_time": True,
            "message": "Selected time does not match your configured slot intervals.",
        }

    # =====================================================
    # 🔁 Anti-duplicados por contacto activo (chat/whatsapp/widget)
    # =====================================================
    now_iso = now_utc.isoformat()
    email_value = (payload.user_email or "").strip().lower()
    phone_value = (payload.user_phone or "").strip()

    active_candidates = []
    if email_value:
        by_email = (
            supabase
            .table("appointments")
            .select(
                "id, client_id, scheduled_time, status, user_name, user_email, "
                "user_phone, appointment_type, recipient_language, recipient_locale"
            )
            .eq("client_id", str(payload.client_id))
            .eq("status", "confirmed")
            .eq("user_email", email_value)
            .gte("scheduled_time", now_iso)
            .order("scheduled_time", desc=False)
            .limit(1)
            .execute()
        )
        if by_email.data:
            active_candidates.extend(by_email.data)

    if phone_value:
        by_phone = (
            supabase
            .table("appointments")
            .select(
                "id, client_id, scheduled_time, status, user_name, user_email, "
                "user_phone, appointment_type, recipient_language, recipient_locale"
            )
            .eq("client_id", str(payload.client_id))
            .eq("status", "confirmed")
            .eq("user_phone", phone_value)
            .gte("scheduled_time", now_iso)
            .order("scheduled_time", desc=False)
            .limit(1)
            .execute()
        )
        if by_phone.data:
            active_candidates.extend(by_phone.data)

    existing_active = None
    if active_candidates:
        active_candidates.sort(key=lambda x: x.get("scheduled_time") or "")
        existing_active = active_candidates[0]

    if existing_active and not payload.replace_existing:
        return {
            "success": False,
            "duplicate_active": True,
            "existing_appointment": {
                "id": existing_active.get("id"),
                "scheduled_time": existing_active.get("scheduled_time"),
                "status": existing_active.get("status"),
            },
            "message": "Active appointment already exists for this contact.",
        }

    existing_id_to_replace = None
    existing_to_replace_snapshot = None
    if existing_active and payload.replace_existing:
        existing_id_to_replace = existing_active.get("id")
        existing_to_replace_snapshot = existing_active

    # =====================================================
    # 🚫 Overlap de horario (no permite dos confirmadas al mismo tiempo)
    # =====================================================
    overlap_window_start = (scheduled_utc - slot_delta).isoformat()
    overlap_window_end = (scheduled_utc + slot_delta).isoformat()
    overlap_query = (
        supabase
        .table("appointments")
        .select("id, scheduled_time, status, user_name, user_email, user_phone")
        .eq("client_id", str(payload.client_id))
        .eq("status", "confirmed")
        .gte("scheduled_time", overlap_window_start)
        .lt("scheduled_time", overlap_window_end)
    )
    if existing_id_to_replace:
        overlap_query = overlap_query.neq("id", existing_id_to_replace)
    overlap_res = overlap_query.execute()
    overlap_existing = None
    for candidate in (overlap_res.data or []):
        raw_start = candidate.get("scheduled_time")
        if not raw_start:
            continue
        try:
            cand_start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
            if cand_start.tzinfo is None:
                cand_start = cand_start.replace(tzinfo=timezone.utc)
            cand_end = cand_start + slot_delta
            if cand_start < (scheduled_utc + slot_delta) and cand_end > scheduled_utc:
                overlap_existing = candidate
                break
        except Exception:
            continue

    if overlap_existing:
        return {
            "success": False,
            "overlap_conflict": True,
            "existing_appointment": {
                "id": overlap_existing.get("id"),
                "scheduled_time": overlap_existing.get("scheduled_time"),
                "status": overlap_existing.get("status"),
                "user_name": overlap_existing.get("user_name"),
                "user_email": overlap_existing.get("user_email"),
                "user_phone": overlap_existing.get("user_phone"),
            },
            "message": "This time is no longer available.",
        }

    # =====================================================
    # 📥 Google -> Evolvian (unidirectional busy guard)
    # =====================================================
    try:
        google_busy = _is_google_slot_busy(
            str(payload.client_id),
            scheduled_utc,
            scheduled_utc + slot_delta,
        )
    except Exception as e:
        logger.error(
            "❌ Google busy check failed | client_id=%s | error=%s",
            str(payload.client_id),
            e,
        )
        return {
            "success": False,
            "invalid_time": True,
            "google_sync_check_failed": True,
            "message": "Could not verify Google Calendar availability. Please try again.",
        }

    if google_busy:
        return {
            "success": False,
            "overlap_conflict": True,
            "google_busy": True,
            "existing_appointment": {},
            "message": "This time is no longer available. Please choose another time.",
        }

    if existing_id_to_replace:
        replacement_cancellation_whatsapp_sent = False
        now_iso_update = datetime.utcnow().isoformat()

        supabase.table("appointments").update({
            "status": "cancelled",
            "updated_at": now_iso_update,
        }).eq("id", existing_id_to_replace).execute()

        supabase.table("appointment_reminders").update({
            "status": "cancelled",
            "updated_at": now_iso_update,
        }).eq("appointment_id", existing_id_to_replace).in_("status", ["pending", "processing"]).execute()

        if existing_to_replace_snapshot:
            cancellation_payload = {
                "id": existing_id_to_replace,
                "client_id": existing_to_replace_snapshot.get("client_id") or str(payload.client_id),
                "user_name": existing_to_replace_snapshot.get("user_name"),
                "user_email": existing_to_replace_snapshot.get("user_email"),
                "user_phone": existing_to_replace_snapshot.get("user_phone"),
                "scheduled_time": existing_to_replace_snapshot.get("scheduled_time"),
                "appointment_type": existing_to_replace_snapshot.get("appointment_type"),
                "recipient_language": existing_to_replace_snapshot.get("recipient_language"),
                "recipient_locale": existing_to_replace_snapshot.get("recipient_locale"),
            }

            try:
                replacement_cancellation_whatsapp_sent = await send_appointment_cancellation_notification(cancellation_payload)
            except Exception:
                logger.exception(
                    "❌ Replaced appointment cancellation WhatsApp notification crashed | client_id=%s | appointment_id=%s",
                    str(payload.client_id),
                    existing_id_to_replace,
                )

            try:
                send_appointment_cancellation_email_notification(cancellation_payload)
            except Exception:
                logger.exception(
                    "❌ Replaced appointment cancellation email notification crashed | client_id=%s | appointment_id=%s",
                    str(payload.client_id),
                    existing_id_to_replace,
                )
    else:
        replacement_cancellation_whatsapp_sent = False

    recipient_language, recipient_locale = _resolve_payload_recipient_language(payload)
    appointment_data = {
        "client_id": str(payload.client_id),
        "user_name": payload.user_name,
        "user_email": payload.user_email,
        "user_phone": payload.user_phone,
        "scheduled_time": scheduled_utc.isoformat(),
        "appointment_type": payload.appointment_type,
        "channel": payload.channel,
        "status": "confirmed",
        "session_id": str(payload.session_id),
        "recipient_language": recipient_language,
        "recipient_locale": recipient_locale,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    res = supabase.table("appointments").insert(appointment_data).execute()

    if not res.data:
        logger.error("❌ Failed to create appointment")
        raise HTTPException(
            status_code=500,
            detail="Failed to create appointment"
        )

    appointment = res.data[0]
    appointment_id = appointment["id"]

    logger.info(f"✅ Appointment created: {appointment_id}")

    try:
        _capture_inline_contact_consent(payload)
    except Exception as consent_error:
        logger.warning(
            "⚠️ Inline consent capture failed | client_id=%s | appointment_id=%s | error=%s",
            str(payload.client_id),
            appointment_id,
            consent_error,
        )

    # 🔔 Instant confirmation (NO cambiado)
    try:
        # Ensure fields are present even if insert response is partial.
        appointment_for_confirmation = {
            "id": appointment.get("id") or appointment_id,
            "client_id": appointment.get("client_id") or str(payload.client_id),
            "user_name": appointment.get("user_name") or payload.user_name,
            "user_email": appointment.get("user_email") or payload.user_email,
            "user_phone": appointment.get("user_phone") or payload.user_phone,
            "scheduled_time": appointment.get("scheduled_time") or scheduled_utc.isoformat(),
            "appointment_type": appointment.get("appointment_type") or payload.appointment_type,
            "recipient_language": appointment.get("recipient_language") or recipient_language,
            "recipient_locale": appointment.get("recipient_locale") or recipient_locale,
        }

        if existing_id_to_replace and replacement_cancellation_whatsapp_sent:
            # In reschedules, give Meta a brief head start so cancellation is delivered first.
            await asyncio.sleep(1.5)

        await send_appointment_confirmation(appointment_for_confirmation)
        send_appointment_email_confirmation(appointment_for_confirmation)
    except Exception:
        logger.exception(
            "❌ Appointment confirmation crashed unexpectedly"
        )

    # 2️⃣ Track usage (NO cambiado)
    supabase.table("appointment_usage").insert({
        "client_id": str(payload.client_id),
        "appointment_id": appointment_id,
        "channel": payload.channel,
        "action": "created",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # 3️⃣ Create reminders (NO cambiado)
    reminders_created = 0
    reminders_skipped_past_due = 0

    if payload.send_reminders:
        chosen_templates: list[dict] = []
        chosen_ids: set[str] = set()
        reminders_pref = payload.reminders or {}
        now_utc_for_reminders = datetime.now(timezone.utc)
        appointment_language_ctx = {
            "recipient_language": recipient_language,
            "recipient_locale": recipient_locale,
        }

        for channel_name in ("whatsapp", "email"):
            explicit_template_id = (reminders_pref.get(channel_name) or "").strip() if isinstance(reminders_pref, dict) else ""
            template = None

            if explicit_template_id:
                try:
                    exact_res = (
                        supabase
                        .table("message_templates")
                        .select("id, channel, type, frequency, meta_template_id, language_family, locale_code")
                        .eq("id", explicit_template_id)
                        .eq("client_id", str(payload.client_id))
                        .eq("channel", channel_name)
                        .eq("type", "appointment_reminder")
                        .eq("is_active", True)
                        .single()
                        .execute()
                    )
                    template = exact_res.data
                except Exception:
                    template = None
                if template and not template.get("frequency"):
                    template = None

            if not template:
                template = resolve_template_for_appointment(
                    client_id=str(payload.client_id),
                    channel=channel_name,
                    template_type="appointment_reminder",
                    appointment=appointment_language_ctx,
                    require_frequency=True,
                    require_body=(channel_name == "email"),
                )

            if not template:
                continue

            template_id_str = str(template.get("id") or "")
            if not template_id_str or template_id_str in chosen_ids:
                continue
            chosen_ids.add(template_id_str)
            chosen_templates.append(template)

        for template in chosen_templates:
            if template.get("channel") == "whatsapp" and not template.get("meta_template_id"):
                logger.warning(
                    "⚠️ Skipping legacy WhatsApp reminder template without canonical meta_template_id | template_id=%s",
                    template.get("id"),
                )
                continue

            raw_frequency = template.get("frequency")
            if not raw_frequency:
                continue

            try:
                frequency = (
                    json.loads(raw_frequency)
                    if isinstance(raw_frequency, str)
                    else raw_frequency
                )
            except Exception:
                logger.warning(
                    f"⚠️ Invalid frequency JSON for template {template.get('id')}"
                )
                continue

            for rule in frequency:
                offset_minutes = rule.get("offset_minutes")
                if offset_minutes is None:
                    continue

                scheduled_at = scheduled_utc + timedelta(
                    minutes=offset_minutes
                )

                # Do not schedule reminders that are already in the past at creation time.
                if scheduled_at <= now_utc_for_reminders:
                    reminders_skipped_past_due += 1
                    logger.info(
                        "⏭️ Reminder rule skipped (past due at creation) | appointment_id=%s | template_id=%s | offset=%s | scheduled_at=%s | now=%s",
                        appointment_id,
                        template.get("id"),
                        offset_minutes,
                        scheduled_at.isoformat(),
                        now_utc_for_reminders.isoformat(),
                    )
                    continue

                supabase.table("appointment_reminders").insert({
                    "client_id": str(payload.client_id),
                    "appointment_id": appointment_id,
                    "template_id": template["id"],
                    "channel": template["channel"],
                    "scheduled_at": scheduled_at.isoformat(),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }).execute()

                reminders_created += 1

        logger.info(
            "⏰ Reminders created: %s | skipped_past_due=%s",
            reminders_created,
            reminders_skipped_past_due,
        )

    else:
        logger.info("ℹ️ No reminders requested for this appointment")

    return {
        "success": True,
        "appointment_id": appointment_id,
        "scheduled_time": appointment["scheduled_time"],
        "status": appointment["status"],
        "reminders_created": reminders_created,
        "reminders_skipped_past_due": reminders_skipped_past_due,
    }


@router.post("/create_appointment", tags=["Appointments"])
async def create_appointment_http(payload: CreateAppointmentPayload, request: Request):
    """
    HTTP wrapper for appointment creation.
    Keeps internal function return shape for non-HTTP callers while returning
    proper HTTP status codes to frontend/API consumers.
    """
    # Dashboard/API calls must prove tenant ownership. Internal automation
    # can bypass bearer auth via the dedicated internal token.
    if not has_valid_internal_token(request):
        authorize_client_request(request, str(payload.client_id))

    result = await create_appointment(payload)

    if not isinstance(result, dict):
        return result

    if result.get("calendar_inactive"):
        return JSONResponse(status_code=403, content=result)
    if result.get("invalid_time"):
        return JSONResponse(status_code=400, content=result)
    if result.get("duplicate_active") or result.get("overlap_conflict"):
        return JSONResponse(status_code=409, content=result)
    if result.get("success") is False:
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(status_code=200, content=result)
