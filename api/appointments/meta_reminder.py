from fastapi import APIRouter, HTTPException, Request
import logging
from datetime import datetime, timezone

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)
from api.internal_auth import require_internal_request

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
        return None

    phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    return phone if phone.startswith("+") else f"+52{phone}"


def build_appointment_details(appointment: dict) -> str:
    parts = []

    if appointment.get("appointment_type"):
        parts.append(appointment["appointment_type"])

    if appointment.get("scheduled_time"):
        parts.append(appointment["scheduled_time"])

    details = " - ".join(parts).strip()
    return details if details else "Cita programada"


# -------------------------
# Endpoint
# -------------------------
@router.post("/{reminder_id}/send-meta")
async def send_meta_reminder(reminder_id: str, request: Request):
    require_internal_request(request)

    # -------------------------------------------------
    # 1️⃣ Load Reminder
    # -------------------------------------------------
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

    if reminder.get("status") != "pending":
        return {"status": "skipped", "reason": "not pending"}

    if reminder.get("channel") != "whatsapp":
        return {"status": "skipped", "reason": "not whatsapp"}

    # -------------------------------------------------
    # 2️⃣ Lock (avoid double send)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 3️⃣ Load Appointment
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 4️⃣ Prepare Data
    # -------------------------------------------------
    to_number = normalize_phone(appointment.get("user_phone"))
    if not to_number:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    user_name = (appointment.get("user_name") or "Cliente").strip()
    appointment_details = build_appointment_details(appointment)

    template_name = reminder.get("template_name") or "appointment_reminder_v1"

    # -------------------------------------------------
    # 5️⃣ Send via Multi-Tenant Wrapper
    # -------------------------------------------------
    result = await send_whatsapp_template_for_client(
        client_id=reminder["client_id"],
        to_number=to_number,
        template_name=template_name,
        language_code="es_MX",
        parameters=[
            user_name,
            appointment_details,
        ],
        purpose="reminder",
        recipient_email=appointment.get("user_email"),
        policy_source="appointments_meta_reminder",
        policy_source_id=reminder_id,
    )

    if not result["success"]:
        logger.error(
            "❌ Meta reminder failed | reminder_id=%s | error=%s",
            reminder_id,
            result["error"],
        )

        supabase.table("appointment_reminders").update({
            "status": "failed",
            "error_reason": result["error"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", reminder_id).execute()

        raise HTTPException(status_code=500, detail="Meta reminder failed")

    # -------------------------------------------------
    # 6️⃣ Mark Sent
    # -------------------------------------------------
    supabase.table("appointment_reminders").update({
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "meta_message_id": result["meta_message_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", reminder_id).execute()

    return {
        "status": "sent",
        "reminder_id": reminder_id,
        "meta_message_id": result["meta_message_id"],
    }
