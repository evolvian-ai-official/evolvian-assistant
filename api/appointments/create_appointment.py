from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import uuid
import logging

from api.config.config import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================
# Payload
# =========================
class CreateAppointmentPayload(BaseModel):
    client_id: uuid.UUID
    scheduled_time: datetime
    user_name: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    appointment_type: Optional[str] = "general"
    channel: Optional[str] = "chat"
    session_id: uuid.UUID


# =========================
# Endpoint
# =========================
@router.post("/create_appointment", tags=["Appointments"])
def create_appointment(payload: CreateAppointmentPayload):
    """
    Creates an appointment and generates appointment_reminders
    based on active message_templates.frequency offsets.

    🔒 Timezone-safe:
    - Frontend sends local datetime
    - Backend stores everything in UTC
    """

    # =========================
    # 🕒 Normalize scheduled_time to UTC
    # =========================
    LOCAL_TZ = ZoneInfo("America/Mexico_City")  # 🔥 fijo por ahora
    scheduled_local = payload.scheduled_time.replace(tzinfo=LOCAL_TZ)
    scheduled_utc = scheduled_local.astimezone(timezone.utc)

    # =========================
    # 1️⃣ Create appointment
    # =========================
    appointment_data = {
        "client_id": str(payload.client_id),
        "user_name": payload.user_name,
        "user_email": payload.user_email,
        "user_phone": payload.user_phone,
        "scheduled_time": scheduled_utc.isoformat(),  # ✅ UTC
        "appointment_type": payload.appointment_type,
        "channel": payload.channel,
        "status": "confirmed",
        "session_id": str(payload.session_id),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    res = supabase.table("appointments").insert(appointment_data).execute()

    if not res.data:
        logger.error("❌ Failed to create appointment")
        raise HTTPException(status_code=500, detail="Failed to create appointment")

    appointment = res.data[0]
    appointment_id = appointment["id"]

    logger.info(f"✅ Appointment created: {appointment_id}")

    # =========================
    # 2️⃣ Track appointment usage
    # =========================
    supabase.table("appointment_usage").insert({
        "client_id": str(payload.client_id),
        "appointment_id": appointment_id,
        "channel": payload.channel,
        "action": "created",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # =========================
    # 3️⃣ Load reminder templates
    # =========================
    templates_res = (
        supabase
        .table("message_templates")
        .select("id, channel, frequency, template_name, label")
        .eq("client_id", str(payload.client_id))
        .eq("type", "appointment_reminder")
        .eq("is_active", True)
        .execute()
    )

    templates = templates_res.data or []

    # =========================
    # 4️⃣ Create appointment reminders (UTC-safe)
    # =========================
    for template in templates:
        frequency = template.get("frequency") or {}
        offsets = frequency.get("offsets", [])

        for offset in offsets:
            unit = offset.get("unit")
            value = offset.get("value")

            if not unit or value is None:
                continue

            if unit == "days":
                scheduled_at = scheduled_utc - timedelta(days=value)
            elif unit == "hours":
                scheduled_at = scheduled_utc - timedelta(hours=value)
            elif unit == "minutes":
                scheduled_at = scheduled_utc - timedelta(minutes=value)
            else:
                continue  # unidad no soportada

            supabase.table("appointment_reminders").insert({
                "client_id": str(payload.client_id),
                "appointment_id": appointment_id,
                "channel": template["channel"],
                "template_id": template["id"],
                "scheduled_at": scheduled_at.isoformat(),  # ✅ UTC
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()

    # =========================
    # 5️⃣ Response
    # =========================
    return {
        "success": True,
        "appointment_id": appointment_id,
        "scheduled_time": appointment["scheduled_time"],
        "status": appointment["status"],
        "reminders_created": True,
    }
