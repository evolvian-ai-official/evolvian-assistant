from fastapi import APIRouter, Request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from babel.dates import format_datetime

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)
from api.modules.calendar.send_confirmation_email import send_confirmation_email
from api.appointments.cancel_link_tokens import build_cancel_link, generate_cancel_token
from api.appointments.template_language_resolution import resolve_locale_for_rendering
from api.internal_auth import require_internal_request

router = APIRouter()
logger = logging.getLogger(__name__)
LANGUAGE_TO_LOCALE = {"es": "es_MX", "en": "en_US"}
MAX_REMINDER_LAG_MINUTES = 20


def get_client_locale(client_id: str) -> str:
    try:
        res = (
            supabase
            .table("client_settings")
            .select("language")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        lang = ((res.data or [{}])[0].get("language") or "es").strip().lower()
        return LANGUAGE_TO_LOCALE.get("en" if lang.startswith("en") else "es", "es_MX")
    except Exception as e:
        logger.warning("⚠️ Failed to get locale | client_id=%s | error=%s", client_id, e)
        return "es_MX"

# =====================================================
# Timezone helper (multi-tenant safe)
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

        tz_str = res.data[0].get("timezone") or "UTC"
        return ZoneInfo(tz_str)

    except Exception as e:
        logger.error("❌ Failed to get timezone | client_id=%s | error=%s", client_id, e)
        return ZoneInfo("UTC")


# =====================================================
# Helpers
# =====================================================
def format_scheduled_time(
    iso_utc: str,
    client_id: str,
    locale_code: str = "es_MX",
) -> str:
    try:
        iso_utc = iso_utc.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(iso_utc)

        client_tz = get_client_timezone(client_id)
        dt_local = dt_utc.astimezone(client_tz)

        return format_datetime(
            dt_local,
            "EEEE, MMMM dd, hh:mm a" if str(locale_code).lower().startswith("en") else "EEEE dd 'de' MMMM, hh:mm a",
            locale=locale_code,
        )

    except Exception as e:
        logger.warning(
            "⚠️ Failed to format scheduled_time | value=%s | client_id=%s | error=%s",
            iso_utc,
            client_id,
            e,
        )
        return ""


def render_template(body: str, appointment: dict, locale_code: str) -> str:
    scheduled_time_label = ""
    appointment_date = ""
    appointment_time = ""
    scheduled_time = appointment.get("scheduled_time")
    client_id = appointment.get("client_id")
    safe_client_id = client_id or ""
    cancel_link = str(appointment.get("_cancel_appointment_link") or "").strip()
    cancel_button_html = (
        f"<a href=\"{cancel_link}\" "
        "style=\"display:inline-block;padding:10px 16px;background:#f8fafc;color:#334155;"
        f"text-decoration:none;border:1px solid #d1d5db;border-radius:8px;font-weight:600;\">{'Cancel appointment' if str(locale_code).lower().startswith('en') else 'Cancelar cita'}</a>"
        if cancel_link else ""
    )

    if scheduled_time:
        scheduled_time_label = format_scheduled_time(
            scheduled_time,
            safe_client_id,
            locale_code,
        )
        try:
            dt_utc = datetime.fromisoformat(str(scheduled_time).replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(get_client_timezone(safe_client_id))
            appointment_date = format_datetime(
                dt_local,
                "EEEE, MMMM dd yyyy" if str(locale_code).lower().startswith("en") else "EEEE dd 'de' MMMM yyyy",
                locale=locale_code,
            )
            appointment_time = format_datetime(
                dt_local,
                "hh:mm a",
                locale=locale_code,
            )
        except Exception:
            appointment_date = ""
            appointment_time = ""

    return (
        body
        .replace("{{user_name}}", appointment.get("user_name", "") or "")
        .replace("{{company_name}}", get_client_company_name(safe_client_id))
        .replace("{{scheduled_time}}", scheduled_time_label or "")
        .replace("{{appointment_date}}", appointment_date or "")
        .replace("{{appointment_time}}", appointment_time or "")
        .replace(
            "{{current_date}}",
            format_datetime(
                datetime.now(get_client_timezone(safe_client_id)),
                "EEEE, MMMM dd yyyy" if str(locale_code).lower().startswith("en") else "EEEE dd 'de' MMMM yyyy",
                locale=locale_code,
            ),
        )
        .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
        .replace("{{cancel_appointment_link}}", cancel_link)
        .replace("{{cancel_appointment_button}}", cancel_button_html)
    )


def get_client_company_name(client_id: str) -> str:
    default_name = "su empresa"

    if not client_id:
        return default_name
    if str(get_client_locale(client_id)).lower().startswith("en"):
        default_name = "your company"

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
        logger.warning(
            "⚠️ Failed loading company_name from client_profile | client_id=%s | error=%s",
            client_id,
            e,
        )

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
        logger.warning(
            "⚠️ Failed loading client_name from clients table | client_id=%s | error=%s",
            client_id,
            e,
        )

    return default_name


def build_reminder_parameters(
    expected_params: int,
    *,
    user_name: str,
    company_name: str,
    appointment_details: str,
    appointment_type: str,
) -> list[str]:
    safe_user = (user_name or "Cliente").strip() or "Cliente"
    safe_company = (company_name or "su empresa").strip() or "su empresa"
    safe_details = (appointment_details or "Cita programada").strip() or "Cita programada"
    safe_type = (appointment_type or "Cita").strip() or "Cita"

    if expected_params <= 0:
        return []
    if expected_params == 1:
        return [safe_details]
    if expected_params == 2:
        return [safe_user, safe_details]
    if expected_params == 3:
        return [safe_user, safe_company, safe_details]

    base = [safe_user, safe_company, safe_details, safe_type]
    if expected_params <= len(base):
        return base[:expected_params]

    return base + ["Información de cita"] * (expected_params - len(base))


# =====================================================
# Endpoint
# =====================================================
@router.post("/reminders/execute")
async def execute_pending_reminders(request: Request):
    require_internal_request(request)

    now = datetime.now(timezone.utc)
    logger.info("⏱️ REMINDER EXECUTION START | now=%s", now.isoformat())

    response = (
        supabase
        .table("appointment_reminders")
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_at", now.isoformat())
        .order("scheduled_at")
        .execute()
    )

    reminders = response.data or []
    logger.info("📥 Pending reminders fetched | count=%s", len(reminders))

    processed = sent = failed = skipped = 0

    for reminder in reminders:
        processed += 1

        reminder_id = reminder["id"]
        appointment_id = reminder["appointment_id"]
        client_id = reminder["client_id"]
        channel = reminder["channel"]

        # Claim reminder atomically to avoid duplicate sends in overlapping cron runs.
        try:
            claim_res = (
                supabase
                .table("appointment_reminders")
                .update({
                    "status": "processing",
                    "updated_at": now.isoformat(),
                })
                .eq("id", reminder_id)
                .eq("status", "pending")
                .execute()
            )
            claimed_rows = claim_res.data or []
            if not claimed_rows:
                skipped += 1
                logger.info(
                    "⏭️ REMINDER SKIPPED (already claimed/processed) | id=%s",
                    reminder_id,
                )
                continue
        except Exception:
            skipped += 1
            logger.exception(
                "❌ REMINDER CLAIM FAILED | id=%s | appointment_id=%s | client_id=%s",
                reminder_id,
                appointment_id,
                client_id,
            )
            continue

        logger.info(
            "🔔 Processing reminder | id=%s | client_id=%s | channel=%s",
            reminder_id,
            client_id,
            channel,
        )

        try:
            # Skip stale reminders that are too late (prevents clustered sends after cron outages).
            scheduled_at_raw = reminder.get("scheduled_at")
            if scheduled_at_raw:
                try:
                    scheduled_at_dt = datetime.fromisoformat(
                        str(scheduled_at_raw).replace("Z", "+00:00")
                    )
                    if scheduled_at_dt.tzinfo is None:
                        scheduled_at_dt = scheduled_at_dt.replace(tzinfo=timezone.utc)
                    else:
                        scheduled_at_dt = scheduled_at_dt.astimezone(timezone.utc)

                    if now - scheduled_at_dt > timedelta(minutes=MAX_REMINDER_LAG_MINUTES):
                        skipped += 1
                        logger.info(
                            "⏭️ REMINDER SKIPPED (stale lag) | reminder_id=%s | scheduled_at=%s | now=%s | lag_minutes=%s",
                            reminder_id,
                            scheduled_at_dt.isoformat(),
                            now.isoformat(),
                            int((now - scheduled_at_dt).total_seconds() // 60),
                        )
                        supabase.table("appointment_reminders").update({
                            "status": "cancelled",
                            "updated_at": now.isoformat(),
                        }).eq("id", reminder_id).execute()
                        continue
                except Exception:
                    logger.exception(
                        "⚠️ Failed parsing reminder scheduled_at for stale check | reminder_id=%s | raw=%s",
                        reminder_id,
                        scheduled_at_raw,
                    )

            # -------------------------------------------------
            # 1️⃣ Load Appointment
            # -------------------------------------------------
            appointment_res = (
                supabase
                .table("appointments")
                .select("*")
                .eq("id", appointment_id)
                .single()
                .execute()
            )

            appointment = appointment_res.data
            if not appointment:
                raise Exception("Appointment not found")

            # Skip overdue reminders for appointments that already passed.
            scheduled_time_raw = appointment.get("scheduled_time")
            if scheduled_time_raw:
                try:
                    appointment_dt = datetime.fromisoformat(
                        str(scheduled_time_raw).replace("Z", "+00:00")
                    )
                    if appointment_dt.tzinfo is None:
                        appointment_dt = appointment_dt.replace(tzinfo=timezone.utc)
                    else:
                        appointment_dt = appointment_dt.astimezone(timezone.utc)

                    if appointment_dt <= now:
                        skipped += 1
                        logger.info(
                            "⏭️ REMINDER SKIPPED (appointment already passed) | reminder_id=%s | appointment_id=%s | appointment_time=%s",
                            reminder_id,
                            appointment_id,
                            appointment_dt.isoformat(),
                        )
                        supabase.table("appointment_reminders").update({
                            "status": "cancelled",
                            "updated_at": now.isoformat(),
                        }).eq("id", reminder_id).execute()
                        continue
                except Exception:
                    logger.exception(
                        "⚠️ Failed parsing appointment scheduled_time for reminder skip check | reminder_id=%s | appointment_id=%s | raw=%s",
                        reminder_id,
                        appointment_id,
                        scheduled_time_raw,
                    )

            # -------------------------------------------------
            # 2️⃣ Load Template
            # -------------------------------------------------
            template_res = (
                supabase
                .table("message_templates")
                .select("*")
                .eq("id", reminder["template_id"])
                .eq("client_id", client_id)
                .eq("is_active", True)
                .single()
                .execute()
            )

            template = template_res.data
            if not template:
                raise Exception("Template not found or inactive")

            logger.info(
                "🧩 Template resolved | id=%s | name=%s",
                template["id"],
                template.get("template_name"),
            )

            send_ok = False

            # =====================================================
            # WHATSAPP
            # =====================================================
            if channel == "whatsapp":

                phone = appointment.get("user_phone")
                if not phone:
                    raise Exception("Missing phone")

                # =====================================================
                # META TEMPLATE FLOW
                # =====================================================
                meta_template_id = template.get("meta_template_id")
                if not meta_template_id:
                    raise Exception(
                        "Legacy WhatsApp reminder template is not allowed. "
                        "Template must reference meta_approved_templates via meta_template_id."
                    )

                template_name = template.get("template_name")
                if not template_name:
                    raise Exception("Template missing template_name")

                meta_res = (
                    supabase
                    .table("meta_approved_templates")
                    .select("parameter_count, language, is_active")
                    .eq("id", meta_template_id)
                    .eq("is_active", True)
                    .single()
                    .execute()
                )

                meta_template = meta_res.data
                if not meta_template:
                    raise Exception(
                        "Meta approved template metadata not found: "
                        f"template_name={template_name}, meta_template_id={meta_template_id}"
                    )

                expected_params = meta_template["parameter_count"]
                language_code = meta_template["language"]
                locale_code = language_code

                raw_user_name = appointment.get("user_name") or "Cliente"
                raw_type = appointment.get("appointment_type") or ""
                raw_time = appointment.get("scheduled_time")

                user_name = raw_user_name.strip() or "Cliente"

                details_parts = []

                if raw_type.strip():
                    details_parts.append(raw_type.strip())

                if raw_time:
                    formatted_time = format_scheduled_time(
                        raw_time,
                        client_id,
                        locale_code,
                    )
                    if formatted_time.strip():
                        details_parts.append(formatted_time)

                appointment_details = " - ".join(details_parts).strip()
                if not appointment_details:
                    appointment_details = "Cita programada"

                parameters = build_reminder_parameters(
                    expected_params,
                    user_name=user_name,
                    company_name=get_client_company_name(client_id),
                    appointment_details=appointment_details,
                    appointment_type=raw_type,
                )

                if expected_params != len(parameters):
                    raise Exception(
                        f"Parameter count mismatch | expected={expected_params} | got={len(parameters)}"
                    )

                logger.info(
                    "📤 Sending META TEMPLATE | reminder_id=%s | template=%s | params=%s",
                    reminder_id,
                    template_name,
                    parameters,
                )

                send_result = await send_whatsapp_template_for_client(
                    client_id=client_id,
                    to_number=phone,
                    template_name=template_name,
                    language_code=language_code,
                    parameters=parameters,
                    purpose="reminder",
                    recipient_email=appointment.get("user_email"),
                    policy_source="appointments_execute_reminders",
                    policy_source_id=reminder_id,
                )
                send_ok = bool(send_result and send_result.get("success"))
                if not send_ok:
                    raise Exception(
                        f"Meta template send failed: {(send_result or {}).get('error', 'unknown error')}"
                    )

            # =====================================================
            # EMAIL
            # =====================================================
            elif channel == "email":

                email = appointment.get("user_email")
                if not email:
                    raise Exception("Missing email")

                _, locale_code = resolve_locale_for_rendering(
                    client_id=client_id,
                    appointment=appointment,
                    template_row=template,
                )
                date_str = ""
                hour_str = ""
                try:
                    scheduled_raw = appointment.get("scheduled_time")
                    if scheduled_raw:
                        dt_utc = datetime.fromisoformat(str(scheduled_raw).replace("Z", "+00:00"))
                        dt_local = dt_utc.astimezone(get_client_timezone(client_id))
                        date_str = format_datetime(dt_local, "yyyy-MM-dd", locale=locale_code)
                        hour_str = format_datetime(dt_local, "HH:mm", locale=locale_code)
                except Exception:
                    date_str = ""
                    hour_str = ""

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

                appointment_for_render = dict(appointment or {})
                appointment_for_render["_cancel_appointment_link"] = cancel_link
                rendered_body = render_template(
                    template.get("body", "") or "",
                    appointment_for_render,
                    locale_code,
                )
                rendered_subject = (
                    (template.get("label") or "").replace("\r", " ").replace("\n", " ").strip()
                    or ("⏰ Appointment reminder" if str(locale_code).lower().startswith("en") else "⏰ Recordatorio de tu cita")
                )

                logger.info(
                    "📧 EMAIL reminder send | to=%s | reminder_id=%s | cancel_link=%s",
                    email,
                    reminder_id,
                    "yes" if cancel_link else "no",
                )

                send_ok = bool(
                    send_confirmation_email(
                        to_email=email,
                        date_str=date_str,
                        hour_str=hour_str,
                        html_body=rendered_body,
                        subject=rendered_subject,
                        client_id=client_id,
                        user_name=appointment.get("user_name"),
                        appointment_type=appointment.get("appointment_type"),
                        purpose="reminder",
                    )
                )
                if not send_ok:
                    raise Exception("Email reminder send failed")

            else:
                raise Exception(f"Unsupported channel: {channel}")

            if not send_ok:
                raise Exception("Provider send failed")

            supabase.table("appointment_reminders").update({
                "status": "sent",
                "updated_at": now.isoformat(),
            }).eq("id", reminder_id).execute()

            sent += 1
            logger.info("✅ REMINDER SENT | id=%s", reminder_id)

        except Exception:
            failed += 1

            logger.exception(
                "❌ REMINDER FAILED | id=%s | appointment_id=%s | client_id=%s",
                reminder_id,
                appointment_id,
                client_id,
            )

            supabase.table("appointment_reminders").update({
                "status": "failed",
                "updated_at": now.isoformat(),
            }).eq("id", reminder_id).execute()

    logger.info(
        "📊 REMINDER SUMMARY | processed=%s | sent=%s | failed=%s | skipped=%s",
        processed,
        sent,
        failed,
        skipped,
    )

    return {
        "processed": processed,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
    }
