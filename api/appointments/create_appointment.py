from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict
import uuid
import logging
import json
from babel.dates import format_datetime

from api.config.config import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_template_for_client,
)
from api.modules.calendar.send_confirmation_email import send_confirmation_email

router = APIRouter()
logger = logging.getLogger(__name__)

TIMEZONE_ALIASES = {
    "america new york time": "America/New_York",
    "america/newyork": "America/New_York",
    "new york": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "america mexico city": "America/Mexico_City",
    "mexico city": "America/Mexico_City",
    "cst": "America/Mexico_City",
}

WEEKDAY_MAP = {
    "mon": 0, "monday": 0, "lun": 0, "lunes": 0,
    "tue": 1, "tuesday": 1, "mar": 1, "martes": 1,
    "wed": 2, "wednesday": 2, "mie": 2, "miercoles": 2, "miércoles": 2,
    "thu": 3, "thursday": 3, "jue": 3, "jueves": 3,
    "fri": 4, "friday": 4, "vie": 4, "viernes": 4,
    "sat": 5, "saturday": 5, "sab": 5, "sabado": 5, "sábado": 5,
    "sun": 6, "sunday": 6, "dom": 6, "domingo": 6,
}


def is_calendar_active_for_client(client_id: str) -> bool:
    """
    Master flag for appointments. If inactive, no new appointments can be created
    from any channel (manual, chat, widget, whatsapp).
    """
    try:
        res = (
            supabase
            .table("calendar_settings")
            .select("calendar_status")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        status = (res.data or [{}])[0].get("calendar_status")
        return status == "active"
    except Exception as e:
        logger.error(f"❌ Failed to check calendar_status for {client_id}: {e}")
        return False


def _normalize_selected_days(raw_days) -> set[int]:
    if not raw_days:
        return {0, 1, 2, 3, 4}
    if isinstance(raw_days, str):
        raw_days = [d.strip() for d in raw_days.split(",") if d.strip()]

    out: set[int] = set()
    for item in (raw_days or []):
        if isinstance(item, int):
            if 0 <= item <= 6:
                out.add(item)
            continue
        key = str(item).strip().lower()
        key = key.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if key in WEEKDAY_MAP:
            out.add(WEEKDAY_MAP[key])
    return out or {0, 1, 2, 3, 4}


def _load_calendar_rules(client_id: str) -> dict:
    defaults = {
        "selected_days": {0, 1, 2, 3, 4},
        "start_time": "09:00",
        "end_time": "18:00",
        "slot_duration_minutes": 30,
        "buffer_minutes": 15,
        "min_notice_hours": 0,
        "allow_same_day": True,
        "max_days_ahead": 365,
    }
    try:
        res = (
            supabase
            .table("calendar_settings")
            .select(
                "selected_days, start_time, end_time, slot_duration_minutes, "
                "buffer_minutes, min_notice_hours, allow_same_day, max_days_ahead"
            )
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        data = (res.data or [{}])[0]
    except Exception:
        data = {}

    def _value_or_default(key: str):
        val = data.get(key)
        return defaults[key] if val is None else val

    return {
        "selected_days": _normalize_selected_days(data.get("selected_days") or defaults["selected_days"]),
        "start_time": _value_or_default("start_time"),
        "end_time": _value_or_default("end_time"),
        "slot_duration_minutes": max(5, min(int(_value_or_default("slot_duration_minutes")), 240)),
        "buffer_minutes": max(0, min(int(_value_or_default("buffer_minutes")), 240)),
        "min_notice_hours": max(0, min(int(_value_or_default("min_notice_hours")), 720)),
        "allow_same_day": bool(data.get("allow_same_day", defaults["allow_same_day"])),
        "max_days_ahead": max(1, min(int(_value_or_default("max_days_ahead")), 365)),
    }


# =====================================================
# Timezone helper (solo agregado, no cambia lógica)
# =====================================================
def get_client_timezone(client_id: str) -> ZoneInfo:
    try:
        res = (
            supabase
            .table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if not res.data:
            return ZoneInfo("UTC")

        tz_raw = (res.data[0].get("timezone") or "UTC").strip()
        tz_key = tz_raw.lower().replace("_", " ").replace("/", " ").strip()
        tz_str = TIMEZONE_ALIASES.get(tz_key, tz_raw)

        # Try common normalization: "America New York Time" -> "America/New_York"
        if " " in tz_str and "/" not in tz_str:
            compact = "_".join([part for part in tz_str.replace("time", "").split() if part])
            if compact.lower().startswith("america_"):
                tz_str = compact.replace("America_", "America/")

        return ZoneInfo(tz_str)

    except Exception as e:
        logger.error(f"❌ Failed to get timezone: {e}")
        return ZoneInfo("UTC")


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
    replace_existing: bool = False


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

    # 1️⃣ Get active confirmation template
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

    # 2️⃣ Resolve meta template
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
        logger.warning(f"⚠️ Meta template not found: {meta_template_id}")
        return

    template_name = meta.get("template_name")
    language_code = meta.get("language") or "es_MX"

    if not template_name:
        logger.warning("⚠️ Meta template missing template_name")
        return

    logger.info(f"📨 Using template: {template_name}")

    # 3️⃣ Format date using client timezone
    try:
        raw_time = appointment.get("scheduled_time")
        if not raw_time:
            raise Exception("Missing scheduled_time")

        scheduled_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))

        # 🔥 SOLO agregado: usar timezone del cliente
        client_tz = get_client_timezone(str(client_id))
        scheduled_local = scheduled_utc.astimezone(client_tz)

        formatted_date = format_datetime(
            scheduled_local,
            "EEEE dd 'de' MMMM yyyy, hh:mm a",
            locale=language_code,
        )

    except Exception as e:
        logger.error(f"❌ Failed formatting date with Babel: {e}")
        formatted_date = appointment.get("scheduled_time")

    # 4️⃣ Send template (NO cambiado)
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


def send_appointment_email_confirmation(appointment: dict) -> None:
    """
    Sends an immediate email confirmation using Resend when user_email exists.
    Independent from WhatsApp template flow.
    """
    email = appointment.get("user_email")
    raw_time = appointment.get("scheduled_time")
    if not email or not raw_time:
        logger.info("ℹ️ Email confirmation skipped — missing user_email or scheduled_time")
        return

    try:
        scheduled_utc = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        client_id = str(appointment.get("client_id"))
        client_tz = get_client_timezone(client_id) if client_id else ZoneInfo("UTC")
        scheduled_local = scheduled_utc.astimezone(client_tz)

        date_str = scheduled_local.strftime("%Y-%m-%d")
        hour_str = scheduled_local.strftime("%H:%M")

        # Use active email appointment_confirmation template if available.
        subject = None
        html_body = None
        if client_id:
            tpl_res = (
                supabase
                .table("message_templates")
                .select("body, label")
                .eq("client_id", client_id)
                .eq("type", "appointment_confirmation")
                .eq("channel", "email")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            templates = tpl_res.data or []
            if templates and templates[0].get("body"):
                template = templates[0]
                html_body = (
                    template.get("body", "")
                    .replace("{{user_name}}", appointment.get("user_name", "") or "Cliente")
                    .replace(
                        "{{scheduled_time}}",
                        format_datetime(
                            scheduled_local,
                            "EEEE dd 'de' MMMM yyyy, hh:mm a",
                            locale="es_MX",
                        ),
                    )
                    .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
                )
                subject = (template.get("label") or "").strip() or None

        send_confirmation_email(
            email,
            date_str,
            hour_str,
            html_body=html_body,
            subject=subject,
        )
        logger.info("✅ Appointment email confirmation sent to %s", email)
    except Exception as e:
        logger.error("❌ Failed sending appointment email confirmation: %s", e)


# =========================
# Endpoint
# =========================
async def create_appointment(payload: CreateAppointmentPayload):
    if not is_calendar_active_for_client(str(payload.client_id)):
        return {
            "success": False,
            "calendar_inactive": True,
            "message": "Appointments are currently disabled for this client.",
        }

    # 🔥 SOLO agregado: obtener timezone del cliente
    LOCAL_TZ = get_client_timezone(str(payload.client_id))
    rules = _load_calendar_rules(str(payload.client_id))

    if payload.scheduled_time.tzinfo is None:
        scheduled_local = payload.scheduled_time.replace(tzinfo=LOCAL_TZ)
    else:
        scheduled_local = payload.scheduled_time.astimezone(LOCAL_TZ)

    # Guardamos siempre en UTC (esto ya lo hacías)
    scheduled_utc = scheduled_local.astimezone(timezone.utc)
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)

    logger.info(
        "🧪 Appointment validation input | client_id=%s | scheduled_local=%s | rules=%s",
        str(payload.client_id),
        scheduled_local.isoformat(),
        {
            "selected_days": sorted(list(rules.get("selected_days", []))),
            "start_time": rules.get("start_time"),
            "end_time": rules.get("end_time"),
            "slot_duration_minutes": rules.get("slot_duration_minutes"),
            "buffer_minutes": rules.get("buffer_minutes"),
            "min_notice_hours": rules.get("min_notice_hours"),
            "max_days_ahead": rules.get("max_days_ahead"),
            "allow_same_day": rules.get("allow_same_day"),
        },
    )

    # =====================================================
    # 🛡️ Reglas base de agenda (aplican a Admin/Widget/Chat/WhatsApp)
    # =====================================================
    if scheduled_utc < now_utc:
        return {
            "success": False,
            "invalid_time": True,
            "message": "Cannot book past times.",
        }

    if scheduled_utc > (now_utc + timedelta(days=365)):
        return {
            "success": False,
            "invalid_time": True,
            "message": "Cannot book beyond one year.",
        }

    # =====================================================
    # 📐 Reglas de Calendar Setup (también para manual)
    # =====================================================
    start_time = rules["start_time"]
    end_time = rules["end_time"]
    slot_duration_min = rules["slot_duration_minutes"]
    buffer_min = rules["buffer_minutes"]
    min_notice_h = rules["min_notice_hours"]
    max_days_ahead = rules["max_days_ahead"]
    allow_same_day = rules["allow_same_day"]
    selected_days = rules["selected_days"]

    try:
        start_h, start_m = [int(v) for v in str(start_time).split(":", 1)]
        end_h, end_m = [int(v) for v in str(end_time).split(":", 1)]
    except Exception:
        start_h, start_m = 9, 0
        end_h, end_m = 18, 0

    if (end_h, end_m) <= (start_h, start_m):
        start_h, start_m = 9, 0
        end_h, end_m = 18, 0

    if scheduled_local.weekday() not in selected_days:
        return {
            "success": False,
            "invalid_time": True,
            "message": "Selected day is not available for booking.",
        }

    day_start = scheduled_local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    day_end = scheduled_local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    slot_delta = timedelta(minutes=slot_duration_min)
    slot_end_local = scheduled_local + slot_delta

    if scheduled_local < day_start or slot_end_local > day_end:
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Selected time is outside working hours ({start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}).",
        }

    if not allow_same_day and scheduled_local.date() == now_local.date():
        return {
            "success": False,
            "invalid_time": True,
            "message": "Same-day bookings are disabled.",
        }

    if scheduled_local < now_local + timedelta(hours=min_notice_h):
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Minimum notice is {min_notice_h} hour(s).",
        }

    if scheduled_local > now_local + timedelta(days=max_days_ahead):
        return {
            "success": False,
            "invalid_time": True,
            "message": f"Bookings are allowed up to {max_days_ahead} day(s) ahead.",
        }

    step_min = max(1, slot_duration_min + buffer_min)
    scheduled_minutes = (scheduled_local.hour * 60) + scheduled_local.minute
    start_minutes = (start_h * 60) + start_m
    minutes_from_start = scheduled_minutes - start_minutes

    valid_start_minutes = set()
    probe = day_start
    step_delta = timedelta(minutes=step_min)
    while probe + slot_delta <= day_end:
        valid_start_minutes.add((probe.hour * 60) + probe.minute)
        probe += step_delta

    if minutes_from_start < 0 or scheduled_minutes not in valid_start_minutes:
        logger.warning(
            "⚠️ Interval mismatch | scheduled_minutes=%s | start_minutes=%s | minutes_from_start=%s | step=%s | slot=%s | buffer=%s | valid_starts=%s",
            scheduled_minutes,
            start_minutes,
            minutes_from_start,
            step_min,
            slot_duration_min,
            buffer_min,
            sorted(valid_start_minutes),
        )
        return {
            "success": False,
            "invalid_time": True,
            "message": "Selected time does not match your configured slot intervals.",
        }

    # =====================================================
    # 🔁 Anti-duplicados por contacto activo (chat/whatsapp/widget)
    # =====================================================
    now_iso = now_utc.isoformat()
    email_value = (payload.user_email or "").strip().lower()
    phone_value = (payload.user_phone or "").strip()

    active_candidates = []
    if email_value:
        by_email = (
            supabase
            .table("appointments")
            .select("id, scheduled_time, status, user_email, user_phone")
            .eq("client_id", str(payload.client_id))
            .eq("status", "confirmed")
            .eq("user_email", email_value)
            .gte("scheduled_time", now_iso)
            .order("scheduled_time", desc=False)
            .limit(1)
            .execute()
        )
        if by_email.data:
            active_candidates.extend(by_email.data)

    if phone_value:
        by_phone = (
            supabase
            .table("appointments")
            .select("id, scheduled_time, status, user_email, user_phone")
            .eq("client_id", str(payload.client_id))
            .eq("status", "confirmed")
            .eq("user_phone", phone_value)
            .gte("scheduled_time", now_iso)
            .order("scheduled_time", desc=False)
            .limit(1)
            .execute()
        )
        if by_phone.data:
            active_candidates.extend(by_phone.data)

    existing_active = None
    if active_candidates:
        active_candidates.sort(key=lambda x: x.get("scheduled_time") or "")
        existing_active = active_candidates[0]

    if existing_active and not payload.replace_existing:
        return {
            "success": False,
            "duplicate_active": True,
            "existing_appointment": {
                "id": existing_active.get("id"),
                "scheduled_time": existing_active.get("scheduled_time"),
                "status": existing_active.get("status"),
            },
            "message": "Active appointment already exists for this contact.",
        }

    existing_id_to_replace = None
    if existing_active and payload.replace_existing:
        existing_id_to_replace = existing_active.get("id")

    # =====================================================
    # 🚫 Overlap de horario (no permite dos confirmadas al mismo tiempo)
    # =====================================================
    overlap_window_start = (scheduled_utc - slot_delta).isoformat()
    overlap_window_end = (scheduled_utc + slot_delta).isoformat()
    overlap_query = (
        supabase
        .table("appointments")
        .select("id, scheduled_time, status, user_name, user_email, user_phone")
        .eq("client_id", str(payload.client_id))
        .eq("status", "confirmed")
        .gte("scheduled_time", overlap_window_start)
        .lt("scheduled_time", overlap_window_end)
    )
    if existing_id_to_replace:
        overlap_query = overlap_query.neq("id", existing_id_to_replace)
    overlap_res = overlap_query.execute()
    overlap_existing = None
    for candidate in (overlap_res.data or []):
        raw_start = candidate.get("scheduled_time")
        if not raw_start:
            continue
        try:
            cand_start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
            if cand_start.tzinfo is None:
                cand_start = cand_start.replace(tzinfo=timezone.utc)
            cand_end = cand_start + slot_delta
            if cand_start < (scheduled_utc + slot_delta) and cand_end > scheduled_utc:
                overlap_existing = candidate
                break
        except Exception:
            continue

    if overlap_existing:
        return {
            "success": False,
            "overlap_conflict": True,
            "existing_appointment": {
                "id": overlap_existing.get("id"),
                "scheduled_time": overlap_existing.get("scheduled_time"),
                "status": overlap_existing.get("status"),
                "user_name": overlap_existing.get("user_name"),
                "user_email": overlap_existing.get("user_email"),
                "user_phone": overlap_existing.get("user_phone"),
            },
            "message": "This time is no longer available.",
        }

    if existing_id_to_replace:
        supabase.table("appointments").update({
            "status": "cancelled",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", existing_id_to_replace).execute()

        supabase.table("appointment_reminders").update({
            "status": "cancelled",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("appointment_id", existing_id_to_replace).in_("status", ["pending", "processing"]).execute()

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

    # 🔔 Instant confirmation (NO cambiado)
    try:
        # Ensure fields are present even if insert response is partial.
        appointment_for_confirmation = {
            "client_id": appointment.get("client_id") or str(payload.client_id),
            "user_name": appointment.get("user_name") or payload.user_name,
            "user_email": appointment.get("user_email") or payload.user_email,
            "user_phone": appointment.get("user_phone") or payload.user_phone,
            "scheduled_time": appointment.get("scheduled_time") or scheduled_utc.isoformat(),
            "appointment_type": appointment.get("appointment_type") or payload.appointment_type,
        }

        await send_appointment_confirmation(appointment_for_confirmation)
        send_appointment_email_confirmation(appointment_for_confirmation)
    except Exception:
        logger.exception(
            "❌ Appointment confirmation crashed unexpectedly"
        )

    # 2️⃣ Track usage (NO cambiado)
    supabase.table("appointment_usage").insert({
        "client_id": str(payload.client_id),
        "appointment_id": appointment_id,
        "channel": payload.channel,
        "action": "created",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # 3️⃣ Create reminders (NO cambiado)
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

    return {
        "success": True,
        "appointment_id": appointment_id,
        "scheduled_time": appointment["scheduled_time"],
        "status": appointment["status"],
        "reminders_created": reminders_created,
    }


@router.post("/create_appointment", tags=["Appointments"])
async def create_appointment_http(payload: CreateAppointmentPayload):
    """
    HTTP wrapper for appointment creation.
    Keeps internal function return shape for non-HTTP callers while returning
    proper HTTP status codes to frontend/API consumers.
    """
    result = await create_appointment(payload)

    if not isinstance(result, dict):
        return result

    if result.get("calendar_inactive"):
        return JSONResponse(status_code=403, content=result)
    if result.get("invalid_time"):
        return JSONResponse(status_code=400, content=result)
    if result.get("duplicate_active") or result.get("overlap_conflict"):
        return JSONResponse(status_code=409, content=result)
    if result.get("success") is False:
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(status_code=200, content=result)
