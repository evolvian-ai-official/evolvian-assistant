from fastapi import APIRouter
from datetime import datetime, timezone

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message

router = APIRouter()


def render_template(body: str, appointment: dict) -> str:
    """
    Render simple de placeholders permitidos.
    Sin magia, sin validaciones silenciosas.
    """
    return (
        body
        .replace("{{user_name}}", appointment.get("user_name", "") or "")
        .replace("{{scheduled_time}}", appointment.get("scheduled_time", "") or "")
        .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
    )


@router.post("/reminders/execute")
async def execute_pending_reminders():
    """
    Ejecuta reminders pendientes cuyo scheduled_at <= now()

    Reglas:
    - Usa message_templates (type = appointment_reminder)
    - SOLO marca 'sent' si el envío fdue exitoso
    - Marca 'failed' si falta template o falla el envío
    - Registra appointment_usage SOLO si se envió
    """

    now = datetime.now(timezone.utc)

    # 1️⃣ Buscar reminders pendientes y vencidos
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
            # 2️⃣ Cargar appointment
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

            # 3️⃣ Cargar template OBLIGATORIO
            template = (
                supabase
                .table("message_templates")
                .select("*")
                .eq("client_id", client_id)
                .eq("channel", channel)
                .eq("type", "appointment_reminder")
                .eq("is_active", True)
                .single()
                .execute()
            ).data

            if not template:
                raise Exception("Missing active message template")

            message_body = render_template(template["body"], appointment)

            # 4️⃣ Envío por canal
            send_ok = False

            if channel == "whatsapp":
                if not appointment.get("user_phone"):
                    raise Exception("Missing phone")

                send_ok = await send_whatsapp_message(
                    to_number=appointment["user_phone"],
                    text=message_body,
                )

            elif channel == "email":
                if not appointment.get("user_email"):
                    raise Exception("Missing email")

                # 🟡 QA placeholder (email real se conecta después)
                print(
                    f"📧 [EMAIL REMINDER]\n"
                    f"To: {appointment['user_email']}\n"
                    f"Body:\n{message_body}\n"
                )

                # En QA lo consideramos exitoso
                send_ok = True

            else:
                raise Exception(f"Unsupported channel: {channel}")

            # 🚨 No marcar sent si el envío falló
            if not send_ok:
                raise Exception(f"{channel} send failed")

            # 5️⃣ Marcar reminder como enviado
            supabase.table("appointment_reminders").update({
                "status": "sent",
                "updated_at": now.isoformat()
            }).eq("id", reminder_id).execute()

            # 6️⃣ Registrar uso SOLO si se envió
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
