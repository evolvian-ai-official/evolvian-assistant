from fastapi import APIRouter, Request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
from babel.dates import format_datetime

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)
from api.internal_auth import require_internal_request

router = APIRouter()
logger = logging.getLogger(__name__)

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
            "EEEE dd 'de' MMMM, hh:mm a",
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
                "EEEE dd 'de' MMMM yyyy",
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
            format_datetime(datetime.now(get_client_timezone(safe_client_id)), "EEEE dd 'de' MMMM yyyy", locale=locale_code),
        )
        .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
    )


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

        logger.info(
            "🔔 Processing reminder | id=%s | client_id=%s | channel=%s",
            reminder_id,
            client_id,
            channel,
        )

        try:
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
            # EMAIL (stub)
            # =====================================================
            elif channel == "email":

                email = appointment.get("user_email")
                if not email:
                    raise Exception("Missing email")

                logger.info("📧 EMAIL reminder (stub) | to=%s", email)
                send_ok = True

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
