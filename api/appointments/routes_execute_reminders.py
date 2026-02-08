from fastapi import APIRouter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_message_for_client
)

router = APIRouter()

# =====================================================
# Timezone fijo (por ahora)
# =====================================================
MEXICO_TZ = ZoneInfo("America/Mexico_City")


# =====================================================
# Helpers
# =====================================================
def format_scheduled_time(iso_utc: str) -> str:
    """
    Convierte un datetime UTC ISO a horario de México legible.
    Ej:
    2026-02-08T17:00:00+00:00
    -> domingo 8 de febrero, 11:00 AM
    """
    try:
        dt_utc = datetime.fromisoformat(iso_utc)
        dt_local = dt_utc.astimezone(MEXICO_TZ)
        return dt_local.strftime("%A %d de %B, %I:%M %p")
    except Exception:
        # Fallback defensivo
        return iso_utc


def render_template(body: str, appointment: dict) -> str:
    """
    Render explícito de placeholders permitidos.
    El horario SIEMPRE se muestra en horario de México.
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

    - DB y scheduler trabajan en UTC
    - El mensaje al usuario se renderiza en horario de México
    """

    now = datetime.now(timezone.utc)

    # -------------------------------------------------
    # 1️⃣ Buscar reminders pendientes y vencidos
    # -------------------------------------------------
    response = (
        supabase
        .table("appointment_reminders")
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_at", now.isoformat())
        .execute()
    )

    reminders = response.data or []

    processed = 0
    sent = 0
    failed = 0

    for reminder in reminders:
        processed += 1

        reminder_id = reminder["id"]
        appointment_id = reminder["appointment_id"]
        client_id = reminder["client_id"]
        channel = reminder["channel"]

        try:
            # -------------------------------------------------
            # 2️⃣ Cargar appointment
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

            # -------------------------------------------------
            # 3️⃣ Cargar template OBLIGATORIO
            # -------------------------------------------------
            template_id = reminder.get("template_id")

            if not template_id:
                raise Exception("Reminder missing template_id")

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
                raise Exception("Message template not found or inactive")

            # 👉 Render humano aquí
            message_body = render_template(template["body"], appointment)

            # -------------------------------------------------
            # 4️⃣ Envío por canal
            # -------------------------------------------------
            send_ok = False

            if channel == "whatsapp":
                if not appointment.get("user_phone"):
                    raise Exception("Missing phone")

                send_ok = await send_whatsapp_message_for_client(
                    client_id=client_id,
                    to_number=appointment["user_phone"],
                    message=message_body
                )

            elif channel == "email":
                if not appointment.get("user_email"):
                    raise Exception("Missing email")

                print(
                    f"📧 [EMAIL REMINDER]\n"
                    f"To: {appointment['user_email']}\n"
                    f"Body:\n{message_body}\n"
                )
                send_ok = True

            else:
                raise Exception(f"Unsupported channel: {channel}")

            if not send_ok:
                raise Exception(f"{channel} send failed")

            # -------------------------------------------------
            # 5️⃣ Marcar reminder como enviado
            # -------------------------------------------------
            supabase.table("appointment_reminders").update({
                "status": "sent",
                "updated_at": now.isoformat()
            }).eq("id", reminder_id).execute()

            # -------------------------------------------------
            # 6️⃣ Registrar uso
            # -------------------------------------------------
            supabase.table("appointment_usage").insert({
                "client_id": client_id,
                "appointment_id": appointment_id,
                "channel": channel,
                "action": "reminder_sent"
            }).execute()

            sent += 1

        except Exception as e:
            failed += 1
            print(f"❌ Reminder failed {reminder_id}: {e}")

            supabase.table("appointment_reminders").update({
                "status": "failed",
                "updated_at": now.isoformat()
            }).eq("id", reminder_id).execute()

    return {
        "processed": processed,
        "sent": sent,
        "failed": failed
    }
