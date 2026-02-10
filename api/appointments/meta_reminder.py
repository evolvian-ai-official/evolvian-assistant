from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime, timezone

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.meta_template_sender import send_meta_template

router = APIRouter(
    prefix="/appointments/reminders",
    tags=["Appointments", "WhatsApp"]
)

logger = logging.getLogger(__name__)


# -------------------------
# Utils
# -------------------------
def normalize_phone(phone: str) -> str:
    if not phone:
        return phone

    phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    return phone if phone.startswith("+") else f"+52{phone}"


def render_appointment_reminder(appointment: dict) -> str:
    """
    Render simple del detalle de la cita.
    SOLO texto, NO envía mensajes.
    """
    parts = []

    if appointment.get("scheduled_at"):
        parts.append(f"📅 {appointment['scheduled_at']}")

    if appointment.get("appointment_type"):
        parts.append(f"📌 {appointment['appointment_type']}")

    return "\n".join(parts) or "Detalles de tu cita"


# -------------------------
# Endpoint
# -------------------------
@router.post("/{reminder_id}/send-meta")
async def send_meta_reminder(reminder_id: str):

    reminder = (
        supabase
        .table("appointment_reminders")
        .select("*")
        .eq("id", reminder_id)
        .single()
        .execute()
        .data
    )

    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.get("status") != "pending":
        return {"status": "skipped", "reason": "not pending"}

    if reminder.get("channel") != "whatsapp":
        return {"status": "skipped", "reason": "not whatsapp"}

    lock = (
        supabase
        .table("appointment_reminders")
        .update({
            "status": "sending",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", reminder_id)
        .eq("status", "pending")
        .execute()
    )

    if not lock.data:
        return {"status": "skipped", "reason": "already processed"}

    appointment = (
        supabase
        .table("appointments")
        .select("*")
        .eq("id", reminder["appointment_id"])
        .single()
        .execute()
        .data
    )

    if not appointment:
        supabase.table("appointment_reminders").update({
            "status": "failed",
            "error_reason": "appointment not found",
        }).eq("id", reminder_id).execute()

        raise HTTPException(status_code=404, detail="Appointment not found")

    to_number = normalize_phone(appointment.get("user_phone"))
    if not to_number:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    details = render_appointment_reminder(appointment)

    try:
        await send_meta_template(
            to_number=to_number,
            template_name="appointment_reminder_v1",
            language_code="es_MX",
            parameters=[
                appointment.get("user_name", ""),
                details,
            ],
        )
    except Exception as e:
        logger.exception("❌ Meta reminder failed")
        supabase.table("appointment_reminders").update({
            "status": "failed",
            "error_reason": str(e),
        }).eq("id", reminder_id).execute()
        raise HTTPException(status_code=500, detail="Meta reminder failed")

    supabase.table("appointment_reminders").update({
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", reminder_id).execute()

    return {"status": "sent", "reminder_id": reminder_id}
