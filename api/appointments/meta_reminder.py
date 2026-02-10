from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime, timezone

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.meta_template_sender import send_meta_template
from api.appointments.template_renderer import render_appointment_reminder

router = APIRouter(
    prefix="/appointments/reminders",
    tags=["Appointments", "WhatsApp"]
)

logger = logging.getLogger(__name__)


# -------------------------
# Utils
# -------------------------
def normalize_phone(phone: str) -> str:
    """
    Normalize phone to E.164.
    Assumes MX by default if no country code.
    """
    if not phone:
        return phone

    phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not phone.startswith("+"):
        phone = f"+52{phone}"

    return phone


# -------------------------
# Endpoint
# -------------------------
@router.post("/{reminder_id}/send-meta")
async def send_meta_reminder(reminder_id: str):
    """
    Sends a WhatsApp appointment reminder using a Meta-approved template.
    Safe for production (idempotent + optimistic lock).
    """

    # 1️⃣ Fetch reminder
    reminder_res = (
        supabase
        .table("appointment_reminders")
        .select("*")
        .eq("id", reminder_id)
        .single()
        .execute()
    )

    reminder = reminder_res.data
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    # 2️⃣ Guard rails
    if reminder.get("status") != "pending":
        return {
            "status": "skipped",
            "reason": f"reminder status is {reminder.get('status')}",
        }

    if reminder.get("channel") != "whatsapp":
        return {
            "status": "skipped",
            "reason": "reminder channel is not whatsapp",
        }

    # 3️⃣ Optimistic lock (avoid double send)
    lock_res = (
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

    if not lock_res.data:
        return {
            "status": "skipped",
            "reason": "reminder already processed by another worker",
        }

    # 4️⃣ Fetch appointment
    appointment_res = (
        supabase
        .table("appointments")
        .select("*")
        .eq("id", reminder["appointment_id"])
        .single()
        .execute()
    )

    appointment = appointment_res.data
    if not appointment:
        supabase.table("appointment_reminders").update({
            "status": "failed",
            "error_reason": "appointment not found",
        }).eq("id", reminder_id).execute()

        raise HTTPException(status_code=404, detail="Appointment not found")

    # 5️⃣ Prepare data
    to_number = normalize_phone(appointment.get("user_phone"))
    if not to_number:
        supabase.table("appointment_reminders").update({
            "status": "failed",
            "error_reason": "invalid phone number",
        }).eq("id", reminder_id).execute()

        raise HTTPException(status_code=400, detail="Invalid phone number")

    details = render_appointment_reminder(appointment)

    # 6️⃣ Send Meta template (USING ENV CREDS)
    try:
        await send_meta_template(
            to_number=to_number,
            template_name="appointment_reminder_v1",
            language_code="es_MX",  # si hiciera ruido, probamos es / es_419
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

    # 7️⃣ Mark as sent
    supabase.table("appointment_reminders").update({
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", reminder_id).execute()

    logger.info("✅ Meta reminder sent", extra={
        "reminder_id": reminder_id,
        "phone": to_number,
    })

    return {
        "status": "sent",
        "reminder_id": reminder_id,
    }
