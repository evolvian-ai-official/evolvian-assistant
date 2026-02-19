from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid
import logging

from api.config.config import supabase
from api.authz import authorize_client_request

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================
# Payload
# =========================
class CancelAppointmentPayload(BaseModel):
    client_id: uuid.UUID
    appointment_id: uuid.UUID
    reason: Optional[str] = "user_cancelled"


# =========================
# Endpoint
# =========================
@router.post("/appointments/cancel", tags=["Appointments"])
def cancel_appointment(payload: CancelAppointmentPayload, request: Request):
    """
    Soft-cancels an appointment:
    - Updates appointment.status = 'cancelled'
    - Cancels all pending reminders
    - Tracks usage

    ⚠️ No deletes. Fully auditable.
    """

    client_id = str(payload.client_id)
    appointment_id = str(payload.appointment_id)
    authorize_client_request(request, client_id)

    # =========================
    # 1️⃣ Load appointment (ownership + status)
    # =========================
    res = (
        supabase
        .table("appointments")
        .select("id, status")
        .eq("id", appointment_id)
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )

    appointment = res.data

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found for this client"
        )

    # =========================
    # 2️⃣ Idempotency check
    # =========================
    if appointment["status"] == "cancelled":
        logger.info(f"ℹ️ Appointment already cancelled: {appointment_id}")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "status": "cancelled",
            "already_cancelled": True
        }

    # =========================
    # 3️⃣ Cancel appointment
    # =========================
    supabase.table("appointments").update({
        "status": "cancelled",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", appointment_id).execute()

    logger.info(f"❌ Appointment cancelled: {appointment_id}")

    # =========================
    # 4️⃣ Cancel pending reminders
    # =========================
    reminders_res = (
        supabase
        .table("appointment_reminders")
        .update({
            "status": "cancelled",
            "updated_at": datetime.utcnow().isoformat(),
        })
        .eq("appointment_id", appointment_id)
        .eq("client_id", client_id)
        .in_("status", ["pending", "processing"])
        .execute()
    )

    cancelled_reminders = len(reminders_res.data or [])

    logger.info(f"⏰ Reminders cancelled: {cancelled_reminders}")

    # =========================
    # 5️⃣ Track usage
    # =========================
    supabase.table("appointment_usage").insert({
        "client_id": client_id,
        "appointment_id": appointment_id,
        "channel": "system",
        "action": "cancelled",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # =========================
    # 6️⃣ Response
    # =========================
    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": "cancelled",
        "reminders_cancelled": cancelled_reminders,
        "reason": payload.reason,
    }
