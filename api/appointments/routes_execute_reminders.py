from fastapi import APIRouter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_message_for_client,
    send_whatsapp_template_for_client,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# =====================================================
# Timezone fijo (México)
# =====================================================
MEXICO_TZ = ZoneInfo("America/Mexico_City")


# =====================================================
# Helpers
# =====================================================
def format_scheduled_time(iso_utc: str) -> str:
    try:
        iso_utc = iso_utc.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(iso_utc)
        dt_local = dt_utc.astimezone(MEXICO_TZ)
        return dt_local.strftime("%A %d de %B, %I:%M %p")
    except Exception as e:
        logger.warning(
            "⚠️ Failed to format scheduled_time | value=%s | error=%s",
            iso_utc,
            e,
        )
        return ""


def render_template(body: str, appointment: dict) -> str:
    scheduled_time = appointment.get("scheduled_time")
    if scheduled_time:
        scheduled_time = format_scheduled_time(scheduled_time)

    return (
        body
        .replace("{{user_name}}", appointment.get("user_name", "") or "")
        .replace("{{scheduled_time}}", scheduled_time or "")
        .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
    )


# =====================================================
# Endpoint
# =====================================================
@router.post("/reminders/execute")
async def execute_pending_reminders():

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
            # 2️⃣ Load Client Template
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
                # META TEMPLATE FLOW (OFICIAL)
                # =====================================================
                if template.get("template_name"):

                    template_name = template["template_name"]

                    # 🔹 Validar contra meta_approved_templates
                    meta_res = (
                        supabase
                        .table("meta_approved_templates")
                        .select("parameter_count, language, is_active")
                        .eq("template_name", template_name)
                        .eq("is_active", True)
                        .single()
                        .execute()
                    )

                    meta_template = meta_res.data
                    if not meta_template:
                        raise Exception(
                            f"Meta approved template not found: {template_name}"
                        )

                    expected_params = meta_template["parameter_count"]
                    language_code = meta_template["language"]

                    # 🔹 Construir parámetros POSICIONALES
                    raw_user_name = appointment.get("user_name") or "Cliente"
                    raw_type = appointment.get("appointment_type") or ""
                    raw_time = appointment.get("scheduled_time")

                    user_name = raw_user_name.strip() or "Cliente"

                    details_parts = []

                    if raw_type.strip():
                        details_parts.append(raw_type.strip())

                    if raw_time:
                        formatted_time = format_scheduled_time(raw_time)
                        if formatted_time.strip():
                            details_parts.append(formatted_time)

                    appointment_details = " - ".join(details_parts).strip()
                    if not appointment_details:
                        appointment_details = "Cita programada"

                    parameters = [
                        user_name,
                        appointment_details,
                    ]

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

                    send_ok = await send_whatsapp_template_for_client(
                        client_id=client_id,
                        to_number=phone,
                        template_name=template_name,
                        language_code=language_code,
                        parameters=parameters,
                    )

                # =====================================================
                # TEXT FALLBACK (legacy controlado)
                # =====================================================
                else:

                    body = template.get("body")
                    if not body:
                        raise Exception("Text template missing body")

                    message_body = render_template(body, appointment)

                    logger.info(
                        "📤 Sending TEXT fallback | reminder_id=%s",
                        reminder_id,
                    )

                    send_ok = await send_whatsapp_message_for_client(
                        client_id=client_id,
                        to_number=phone,
                        message=message_body,
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

            # -------------------------------------------------
            # 4️⃣ Mark Sent
            # -------------------------------------------------
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
