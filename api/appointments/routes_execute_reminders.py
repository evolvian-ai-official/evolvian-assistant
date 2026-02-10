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
# Timezone fijo (por ahora)
# =====================================================
MEXICO_TZ = ZoneInfo("America/Mexico_City")

# =====================================================
# Helpers
# =====================================================
def format_scheduled_time(iso_utc: str) -> str:
    """
    Convierte ISO UTC a horario México.
    ⚠️ Devuelve string vacío solo si el input es inválido
    """
    try:
        iso_utc = iso_utc.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(iso_utc)
        dt_local = dt_utc.astimezone(MEXICO_TZ)
        return dt_local.strftime("%A %d de %B, %I:%M %p")
    except Exception as e:
        logger.warning("⚠️ Failed to format scheduled_time | value=%s | error=%s", iso_utc, e)
        return ""


def render_template(body: str, appointment: dict) -> str:
    """
    Render simple para fallback de texto (NO Meta templates)
    """
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
    """
    Ejecuta reminders pendientes cuyo scheduled_at <= now()

    Reglas clave:
    - Scheduler trabaja en UTC
    - Mensaje se renderiza en horario México
    - WhatsApp:
        - Usa Meta Templates POSICIONALES si existen
        - Fallback a texto si no
    """

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
            scheduled_at = datetime.fromisoformat(
                reminder["scheduled_at"].replace("Z", "+00:00")
            )

            logger.info(
                "📅 Reminder schedule | id=%s | scheduled_at_utc=%s",
                reminder_id,
                scheduled_at.isoformat(),
            )

            # -------------------------------------------------
            # 1️⃣ Appointment
            # -------------------------------------------------
            appointment = (
                supabase
                .table("appointments")
                .select("*")
                .eq("id", appointment_id)
                .single()
                .execute()
            ).data

            if not appointment:
                raise Exception("Appointment not found")

            logger.info(
                "👤 Appointment loaded | id=%s | phone=%s | email=%s",
                appointment_id,
                appointment.get("user_phone"),
                appointment.get("user_email"),
            )

            # -------------------------------------------------
            # 2️⃣ Template
            # -------------------------------------------------
            template_id = reminder.get("template_id")
            if not template_id:
                raise Exception("Missing template_id")

            template = (
                supabase
                .table("message_templates")
                .select("*")
                .eq("id", template_id)
                .eq("client_id", client_id)
                .eq("is_active", True)
                .single()
                .execute()
            ).data

            if not template:
                raise Exception("Template not found or inactive")

            logger.info(
                "🧩 Template resolved | id=%s | name=%s",
                template_id,
                template.get("template_name"),
            )

            # Texto renderizado (solo fallback)
            message_body = render_template(template["body"], appointment)

            # -------------------------------------------------
            # 3️⃣ Envío
            # -------------------------------------------------
            send_ok = False

            if channel == "whatsapp":
                phone = appointment.get("user_phone")
                if not phone:
                    raise Exception("Missing phone")

                raw_user_name = appointment.get("user_name")
                raw_type = appointment.get("appointment_type")
                raw_time = appointment.get("scheduled_time")

                user_name = raw_user_name.strip() if raw_user_name else "Cliente"

                details_parts = []

                if raw_type and raw_type.strip():
                    details_parts.append(raw_type.strip())

                if raw_time:
                    formatted_time = format_scheduled_time(raw_time)
                    if formatted_time.strip():
                        details_parts.append(formatted_time)

                appointment_details = " - ".join(details_parts)

                # Blindaje final Meta
                if not user_name.strip():
                    user_name = "Cliente"

                if not appointment_details.strip():
                    appointment_details = "Cita programada"

                logger.info(
                    "🧪 META PARAMS READY | reminder_id=%s | params=[%s, %s]",
                    reminder_id,
                    user_name,
                    appointment_details,
                )

                # 🟦 META TEMPLATE
                if template.get("template_name"):
                    logger.info(
                        "📤 Sending META TEMPLATE | reminder_id=%s | template=%s",
                        reminder_id,
                        template["template_name"],
                    )

                    send_ok = await send_whatsapp_template_for_client(
                        client_id=client_id,
                        to_number=phone,
                        template_name=template["template_name"],
                        language_code="es_MX",
                        parameters=[
                            user_name,           # {{1}}
                            appointment_details, # {{2}}
                        ],
                    )

                # 🟩 TEXTO fallback
                else:
                    logger.info(
                        "📤 Sending TEXT fallback | reminder_id=%s",
                        reminder_id,
                    )

                    send_ok = await send_whatsapp_message_for_client(
                        client_id=client_id,
                        to_number=phone,
                        message=message_body,
                    )

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
            # 4️⃣ Mark sent
            # -------------------------------------------------
            supabase.table("appointment_reminders").update({
                "status": "sent",
                "updated_at": now.isoformat(),
            }).eq("id", reminder_id).execute()

            sent += 1
            logger.info("✅ REMINDER SENT | id=%s", reminder_id)

        except Exception as e:
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
