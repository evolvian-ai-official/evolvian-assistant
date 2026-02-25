from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from babel.dates import format_datetime as babel_format_datetime
except Exception:  # pragma: no cover - fallback for lightweight test envs
    babel_format_datetime = None

from api.config.config import supabase
from api.appointments.template_language_resolution import (
    resolve_locale_for_rendering,
    resolve_template_for_appointment,
)
logger = logging.getLogger(__name__)


def _get_client_timezone(client_id: str) -> ZoneInfo:
    try:
        response = (
            supabase
            .table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        timezone_value = ((response.data or [{}])[0].get("timezone") or "UTC").strip() or "UTC"
        return ZoneInfo(timezone_value)
    except Exception:
        return ZoneInfo("UTC")


def _get_client_company_name(client_id: str) -> str:
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
    except Exception:
        logger.exception("⚠️ Failed loading client_profile.company_name | client_id=%s", client_id)

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
    except Exception:
        logger.exception("⚠️ Failed loading clients.name | client_id=%s", client_id)

    return default_name


def build_cancellation_parameters(
    expected_params: int,
    *,
    user_name: str,
    company_name: str,
    appointment_date: str,
    appointment_time: str,
) -> list[str]:
    safe_user = (user_name or "Cliente").strip() or "Cliente"
    safe_company = (company_name or "su empresa").strip() or "su empresa"
    safe_date = (appointment_date or "Fecha por confirmar").strip() or "Fecha por confirmar"
    safe_time = (appointment_time or "Hora por confirmar").strip() or "Hora por confirmar"

    if expected_params <= 0:
        return []
    if expected_params == 1:
        return [safe_user]
    if expected_params == 2:
        return [safe_user, safe_company]
    if expected_params == 3:
        return [safe_user, safe_company, safe_date]

    base = [safe_user, safe_company, safe_date, safe_time]
    if expected_params <= len(base):
        return base[:expected_params]

    return base + ["Información de cancelación"] * (expected_params - len(base))


def _format_cancelled_datetime(
    *,
    client_id: str,
    scheduled_time_raw: str,
    language_code: str,
) -> tuple[str, str]:
    if not scheduled_time_raw:
        return "Fecha por confirmar", "Hora por confirmar"

    try:
        scheduled_utc = datetime.fromisoformat(str(scheduled_time_raw).replace("Z", "+00:00"))
        local_dt = scheduled_utc.astimezone(_get_client_timezone(client_id))
    except Exception:
        return str(scheduled_time_raw), ""

    try:
        if not babel_format_datetime:
            raise ValueError("babel_not_available")
        date_pattern = (
            "EEEE, MMMM dd yyyy"
            if str(language_code).lower().startswith("en")
            else "EEEE dd 'de' MMMM yyyy"
        )
        date_label = babel_format_datetime(
            local_dt,
            date_pattern,
            locale=language_code,
        )
        time_label = babel_format_datetime(
            local_dt,
            "hh:mm a",
            locale=language_code,
        )
        return date_label, time_label
    except Exception:
        return local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M")


def _render_email_template_text(template_text: str | None, replacements: dict[str, str]) -> str | None:
    if template_text is None:
        return None
    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value or "")
    return rendered


async def send_appointment_cancellation_notification(appointment: dict) -> bool:
    from api.modules.whatsapp.whatsapp_sender import send_whatsapp_template_for_client

    client_id = str(appointment.get("client_id") or "").strip()
    to_phone = (appointment.get("user_phone") or "").strip()
    if not client_id or not to_phone:
        logger.info(
            "ℹ️ Appointment cancellation notification skipped — missing client_id or user_phone"
        )
        return False

    template = resolve_template_for_appointment(
        client_id=client_id,
        channel="whatsapp",
        template_type="appointment_cancellation",
        appointment=appointment,
    )
    if not template:
        logger.info("ℹ️ No active appointment_cancellation template found | client_id=%s", client_id)
        return False

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
            "⚠️ Meta template metadata not found for cancellation | meta_template_id=%s",
            meta_template_id,
        )
        return False

    template_name = (meta.get("template_name") or "").strip()
    if not template_name:
        logger.warning("⚠️ Cancellation meta template missing template_name")
        return False

    _, language_code = resolve_locale_for_rendering(
        client_id=client_id,
        appointment=appointment,
        template_row=template,
        meta_row=meta,
    )
    expected_params = int(meta.get("parameter_count") or 4)
    company_name = _get_client_company_name(client_id)

    appointment_date, appointment_time = _format_cancelled_datetime(
        client_id=client_id,
        scheduled_time_raw=str(appointment.get("scheduled_time") or ""),
        language_code=language_code,
    )

    parameters = build_cancellation_parameters(
        expected_params,
        user_name=appointment.get("user_name") or "Cliente",
        company_name=company_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
    )

    send_result = await send_whatsapp_template_for_client(
        client_id=client_id,
        to_number=to_phone,
        template_name=template_name,
        language_code=language_code,
        parameters=parameters,
        purpose="transactional",
        recipient_email=appointment.get("user_email"),
        policy_source="appointments_cancellation",
        policy_source_id=str(appointment.get("id") or ""),
    )

    if not send_result.get("success"):
        logger.error(
            "❌ Appointment cancellation template failed | client_id=%s | appointment_id=%s | error=%s",
            client_id,
            appointment.get("id"),
            send_result.get("error"),
        )
        return False

    logger.info(
        "✅ Appointment cancellation template sent | client_id=%s | appointment_id=%s | message_id=%s",
        client_id,
        appointment.get("id"),
        send_result.get("meta_message_id"),
    )
    return True


def send_appointment_cancellation_email_notification(appointment: dict) -> bool:
    from api.modules.calendar.send_confirmation_email import send_confirmation_email

    client_id = str(appointment.get("client_id") or "").strip()
    to_email = (appointment.get("user_email") or "").strip().lower()
    if not client_id or not to_email:
        logger.info(
            "ℹ️ Appointment cancellation email skipped — missing client_id or user_email"
        )
        return False

    template = resolve_template_for_appointment(
        client_id=client_id,
        channel="email",
        template_type="appointment_cancellation",
        appointment=appointment,
        require_body=True,
    )
    if not template:
        logger.info(
            "ℹ️ No active appointment_cancellation email template found | client_id=%s",
            client_id,
        )
        return False

    _, language_code = resolve_locale_for_rendering(
        client_id=client_id,
        appointment=appointment,
        template_row=template,
    )
    appointment_date, appointment_time = _format_cancelled_datetime(
        client_id=client_id,
        scheduled_time_raw=str(appointment.get("scheduled_time") or ""),
        language_code=language_code,
    )
    company_name = _get_client_company_name(client_id)
    current_date = (
        babel_format_datetime(
            datetime.now(_get_client_timezone(client_id)),
            "EEEE, MMMM dd yyyy" if str(language_code).lower().startswith("en") else "EEEE dd 'de' MMMM yyyy",
            locale=language_code,
        )
        if babel_format_datetime
        else datetime.utcnow().strftime("%Y-%m-%d")
    )
    scheduled_time = f"{appointment_date} {appointment_time}".strip()

    replacements = {
        "company_name": company_name or "",
        "user_name": (appointment.get("user_name") or "Cliente").strip() or "Cliente",
        "user_email": to_email,
        "appointment_type": (appointment.get("appointment_type") or "").strip(),
        "scheduled_time": scheduled_time,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "current_date": current_date,
        "cancel_appointment_link": "",
        "cancel_appointment_button": "",
    }

    rendered_body = _render_email_template_text(template.get("body"), replacements) or ""
    if not rendered_body.strip():
        logger.warning(
            "⚠️ appointment_cancellation email template rendered empty | client_id=%s | template_id=%s",
            client_id,
            template.get("id"),
        )
        return False

    default_subject = (
        "❌ Appointment cancelled"
        if str(language_code).lower().startswith("en")
        else "❌ Tu cita fue cancelada"
    )
    rendered_subject = _render_email_template_text((template.get("label") or "").strip(), replacements) or ""
    subject = rendered_subject.replace("\r", " ").replace("\n", " ").strip() or default_subject

    sent = send_confirmation_email(
        to_email,
        appointment_date,
        appointment_time,
        html_body=rendered_body,
        subject=subject,
        client_id=client_id,
        user_name=appointment.get("user_name"),
        appointment_type=appointment.get("appointment_type"),
        purpose="transactional",
    )
    if sent:
        logger.info(
            "✅ Appointment cancellation email sent | client_id=%s | appointment_id=%s | to=%s",
            client_id,
            appointment.get("id"),
            to_email,
        )
    else:
        logger.warning(
            "⚠️ Appointment cancellation email skipped/blocked | client_id=%s | appointment_id=%s | to=%s",
            client_id,
            appointment.get("id"),
            to_email,
        )
    return bool(sent)
