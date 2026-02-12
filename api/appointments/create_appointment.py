from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict
import uuid
import logging
import json

from api.config.config import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================
# Payload
# =========================
class CreateAppointmentPayload(BaseModel):
    client_id: uuid.UUID
    session_id: uuid.UUID
    scheduled_time: datetime
    user_name: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    appointment_type: Optional[str] = "general"
    channel: Optional[str] = "chat"

    send_reminders: bool = False
    reminders: Optional[Dict[str, Optional[str]]] = None


# =========================
# Internal helper
# =========================
async def send_appointment_confirmation(appointment: dict) -> None:
    client_id = appointment.get("client_id")
    phone = appointment.get("user_phone")

    if not client_id or not phone:
        logger.warning(
            "⚠️ Appointment confirmation skipped — missing client_id or phone"
        )
        return

    # -----------------------------------
    # 1️⃣ Get active confirmation template
    # -----------------------------------
    res = (
        supabase
        .table("message_templates")
        .select("id, meta_template_id")
        .eq("client_id", client_id)
        .eq("type", "appointment_confirmation")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    templates = res.data or []

    if not templates:
        logger.info("ℹ️ No active appointment_confirmation template found")
        return

    template = templates[0]
    meta_template_id = template.get("meta_template_id")

    if not meta_template_id:
        logger.warning("⚠️ Confirmation template has no meta_template_id")
        return

    # -----------------------------------
    # 2️⃣ Resolve meta template manually
    # -----------------------------------
    meta_res = (
        supabase
        .table("meta_approved_templates")
        .select("template_name, language")
        .eq("id", meta_template_id)
        .eq("is_active", True)
        .single()
        .execute()
    )

    meta = meta_res.data

    if not meta:
        logger.warning(
            f"⚠️ Meta template not found: {meta_template_id}"
        )
        return

    template_name = meta.get("template_name")
    language_code = meta.get("language") or "es_MX"

    if not template_name:
        logger.warning("⚠️ Meta template missing template_name")
        return

    logger.info(f"📨 Using template: {template_name}")

    # -----------------------------------
    # 3️⃣ Format date
    # -----------------------------------
    try:
        scheduled_utc = datetime.fromisoformat(
            appointment.get("scheduled_time")
        )

        local_tz = ZoneInfo("America/Mexico_City")
        scheduled_local = scheduled_utc.astimezone(local_tz)

        formatted_date = scheduled_local.strftime(
            "%d de %B %Y, %I:%M %p"
        )

    except Exception as e:
        logger.error(f"❌ Failed formatting date: {e}")
        formatted_date = appointment.get("scheduled_time")

    # -----------------------------------
    # 4️⃣ Send template
    # -----------------------------------
    result = await send_whatsapp_template_for_client(
        client_id=client_id,
        to_number=phone,
        template_name=template_name,
        language_code=language_code,
        parameters=[
            appointment.get("user_name") or "Cliente",
            formatted_date or "Cita programada",
        ],
    )

    if not result["success"]:
        logger.error(
            "❌ Appointment confirmation failed | client_id=%s | error=%s",
            client_id,
            result.get("error"),
        )
    else:
        logger.info(
            "✅ Appointment confirmation sent | message_id=%s",
            result.get("meta_message_id"),
        )

# =========================
# Endpoint
# =========================
@router.post("/create_appointment", tags=["Appointments"])
async def create_appointment(payload: CreateAppointmentPayload):

    # =========================
    # 🕒 Normalize scheduled_time to UTC
    # =========================
    try:
        LOCAL_TZ = ZoneInfo("America/Mexico_City")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid timezone configuration"
        )

    if payload.scheduled_time.tzinfo is None:
        scheduled_local = payload.scheduled_time.replace(tzinfo=LOCAL_TZ)
    else:
        scheduled_local = payload.scheduled_time.astimezone(LOCAL_TZ)

    scheduled_utc = scheduled_local.astimezone(timezone.utc)

    # =========================
    # 1️⃣ Create appointment
    # =========================
    appointment_data = {
        "client_id": str(payload.client_id),
        "user_name": payload.user_name,
        "user_email": payload.user_email,
        "user_phone": payload.user_phone,
        "scheduled_time": scheduled_utc.isoformat(),
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
        raise HTTPException(
            status_code=500,
            detail="Failed to create appointment"
        )

    appointment = res.data[0]
    appointment_id = appointment["id"]

    logger.info(f"✅ Appointment created: {appointment_id}")

    # =========================
    # 🔔 Instant confirmation
    # =========================
    try:
        await send_appointment_confirmation(appointment)
    except Exception:
        logger.exception(
            "❌ Appointment confirmation crashed unexpectedly"
        )

    # =========================
    # 2️⃣ Track usage
    # =========================
    supabase.table("appointment_usage").insert({
        "client_id": str(payload.client_id),
        "appointment_id": appointment_id,
        "channel": payload.channel,
        "action": "created",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # =========================
    # 3️⃣ Create reminders (optional)
    # =========================
    reminders_created = 0

    if payload.send_reminders:

        templates_res = (
            supabase
            .table("message_templates")
            .select("id, channel, frequency")
            .eq("client_id", str(payload.client_id))
            .eq("type", "appointment_reminder")
            .eq("is_active", True)
            .execute()
        )

        templates = templates_res.data or []

        for template in templates:

            raw_frequency = template.get("frequency")
            if not raw_frequency:
                continue

            try:
                frequency = (
                    json.loads(raw_frequency)
                    if isinstance(raw_frequency, str)
                    else raw_frequency
                )
            except Exception:
                logger.warning(
                    f"⚠️ Invalid frequency JSON for template {template.get('id')}"
                )
                continue

            for rule in frequency:
                offset_minutes = rule.get("offset_minutes")
                if offset_minutes is None:
                    continue

                scheduled_at = scheduled_utc + timedelta(
                    minutes=offset_minutes
                )

                supabase.table("appointment_reminders").insert({
                    "client_id": str(payload.client_id),
                    "appointment_id": appointment_id,
                    "template_id": template["id"],
                    "channel": template["channel"],
                    "scheduled_at": scheduled_at.isoformat(),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }).execute()

                reminders_created += 1

        logger.info(f"⏰ Reminders created: {reminders_created}")

    else:
        logger.info("ℹ️ No reminders requested for this appointment")

    # =========================
    # 4️⃣ Response
    # =========================
    return {
        "success": True,
        "appointment_id": appointment_id,
        "scheduled_time": appointment["scheduled_time"],
        "status": appointment["status"],
        "reminders_created": reminders_created,
    }
