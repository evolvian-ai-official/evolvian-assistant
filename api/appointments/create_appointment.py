from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict
import uuid
import logging
import json

from api.config.config import supabase
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message_for_client

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

    # 🔑 CONTROL REAL DE INTENCIÓN
    send_reminders: bool = False

    # opcional (futuro / granular)
    reminders: Optional[Dict[str, Optional[str]]] = None


# =========================
# Internal helper (ASYNC ✅)
# =========================
async def send_appointment_confirmation(appointment: dict) -> None:
    client_id = appointment.get("client_id")
    phone = appointment.get("user_phone")

    if not client_id or not phone:
        logger.warning(
            "⚠️ Appointment confirmation skipped — missing client_id or phone"
        )
        return

    res = (
        supabase
        .table("message_templates")
        .select("channel, body, template_name")
        .eq("client_id", client_id)
        .eq("type", "appointment_confirmation")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    templates = res.data or []

    if not templates:
        logger.info("ℹ️ No appointment_confirmation template found")
        return

    message = (
        "Hola {name} 👋\n"
        "Gracias por agendar esta consulta.\n\n"
        "Detalles: {time}\n\n"
        "Si necesitas más información comunícate directamente con nosotros."
    ).format(
        name=appointment.get("user_name", ""),
        time=appointment.get("scheduled_time", ""),
    )

    await send_whatsapp_message_for_client(
        client_id=client_id,
        to_number=phone,
        message=message,
    )

    logger.info("✅ Appointment confirmation sent (WhatsApp)")


# =========================
# Endpoint
# =========================
@router.post("/create_appointment", tags=["Appointments"])
async def create_appointment(payload: CreateAppointmentPayload):
    """
    Creates an appointment.
    Reminders are created ONLY if user explicitly requested them.
    """

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
    # 🔔 Appointment confirmation (INSTANT)
    # =========================
    try:
        await send_appointment_confirmation(appointment)
    except Exception as e:
        logger.error(
            f"❌ Appointment confirmation failed | "
            f"appointment_id={appointment_id} | error={e}",
            exc_info=True,
        )

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
    # 3️⃣ Create reminders ONLY if requested
    # =========================
    reminders_created = 0

    if not payload.send_reminders:
        logger.info("ℹ️ No reminders requested for this appointment")
    else:
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
