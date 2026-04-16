from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
import logging
import uuid
import re
from zoneinfo import ZoneInfo

from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.utils.usage_limiter import check_and_increment_usage
from api.security.request_limiter import enforce_rate_limit, get_request_ip
from datetime import datetime, timedelta

# 🧠 Nuevo: importamos el intent router
from api.modules.assistant_rag.intent_router import process_user_message
from api.appointments.create_appointment import (
    CreateAppointmentPayload,
    create_appointment as create_appointment_route,
    get_client_timezone,
    _get_google_busy_ranges,
)
from api.appointments.cancel_appointment import _cancel_appointment_record
from api.utils.calendar_feature_flags import (
    client_can_use_calendar_ai_for_channel,
    client_can_use_widget_calendar_booking,
)

router = APIRouter()
ACTIVE_WIDGET_APPOINTMENT_STATUSES = ("confirmed", "scheduled", "pending")
WIDGET_CALENDAR_BLOCKING_STATUSES = (
    "confirmed",
    "scheduled",
    "pending",
    "pending_confirmation",
)

# 🔹 Input model
class ChatRequest(BaseModel):
    public_client_id: str
    session_id: str
    message: str
    channel: str = "chat"


class WidgetBookRequest(BaseModel):
    public_client_id: str
    scheduled_time: str
    user_name: str
    user_email: str | None = None
    user_phone: str | None = None
    session_id: str | None = None
    replace_existing: bool = False


class WidgetCancelLookupRequest(BaseModel):
    public_client_id: str
    user_email: str | None = None
    user_phone: str | None = None


class WidgetCancelConfirmRequest(BaseModel):
    public_client_id: str
    appointment_id: str
    user_email: str | None = None
    user_phone: str | None = None


# 🔎 Obtener límite dinámico de mensajes desde client_settings
def get_max_messages_per_session(client_id: str) -> int:
    """
    Obtiene el límite de mensajes por sesión desde client_settings.
    Si no existe o falla, devuelve 20 como valor por defecto.
    """
    try:
        response = (
            supabase.table("client_settings")
            .select("max_messages_per_session")
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        if not response.data:
            logging.warning(f"⚠️ No se encontró configuración para client_id={client_id}. Usando 20 por defecto.")
            return 20

        value = response.data.get("max_messages_per_session", 20)
        if not isinstance(value, int) or value <= 0:
            logging.warning(f"⚠️ max_messages_per_session inválido ({value}) para {client_id}. Usando 20 por defecto.")
            return 20

        logging.info(f"✅ Límite dinámico de mensajes cargado: {value} para {client_id}")
        return value

    except Exception as e:
        logging.error(f"❌ Error obteniendo max_messages_per_session: {e}")
        return 20


# 🔒 Safely map public_client_id → client_id
def get_client_id_from_public_client_id(public_client_id: str) -> str:
    """Fetch client_id from Supabase using public_client_id."""
    try:
        response = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", public_client_id)
            .execute()
        )
        if not response.data or len(response.data) == 0:
            logging.error(f"❌ No client found for public_client_id={public_client_id}")
            raise ValueError("Client not found for provided public_client_id")

        client_id = response.data[0]["id"]
        uuid.UUID(client_id)  # ensure it's a valid UUID
        return client_id

    except Exception as e:
        logging.exception(f"🔥 Error resolving client_id for public_client_id={public_client_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid or missing client mapping for {public_client_id}")


# 🌍 Detect message language (simple heuristic)
def detect_language(text: str) -> str:
    """
    Detects whether the text is Spanish or English based on common words and characters.
    Returns 'es' or 'en'.
    """
    text_lower = text.lower()

    # Common Spanish signals
    spanish_words = [
        "hola", "gracias", "por favor", "necesito", "quiero", "cómo", "cuál",
        "dónde", "porque", "dame", "tengo", "plan", "ayuda", "mensaje", "precio",
        "cuánto", "qué", "cuando", "cuantos", "favor", "contacto", "correo", "whatsapp"
    ]

    # If special characters exist
    if any(c in text_lower for c in "áéíóúñ¿¡"):
        return "es"

    # If Spanish words are detected
    if any(word in text_lower for word in spanish_words):
        return "es"

    # English default (fallback)
    return "en"


WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "lun": 0,
    "lunes": 0,
    "tue": 1,
    "tuesday": 1,
    "mar": 1,
    "martes": 1,
    "wed": 2,
    "wednesday": 2,
    "mie": 2,
    "miercoles": 2,
    "thursday": 3,
    "thu": 3,
    "jue": 3,
    "jueves": 3,
    "fri": 4,
    "friday": 4,
    "vie": 4,
    "viernes": 4,
    "sat": 5,
    "saturday": 5,
    "sab": 5,
    "sabado": 5,
    "sun": 6,
    "sunday": 6,
    "dom": 6,
    "domingo": 6,
}


def _parse_yyyy_mm_dd(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d")
    except Exception:
        return None


def _normalize_selected_days(raw_days) -> set[int]:
    if not raw_days:
        return {0, 1, 2, 3, 4}
    if isinstance(raw_days, str):
        raw_days = [d.strip() for d in raw_days.split(",") if d.strip()]
    out = set()
    for item in raw_days:
        key = str(item).strip().lower()
        key = key.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if key in WEEKDAY_MAP:
            out.add(WEEKDAY_MAP[key])
    return out or {0, 1, 2, 3, 4}


def _get_widget_calendar_config(client_id: str) -> dict:
    def _as_bool(value, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    default_config = {
        "calendar_status": "inactive",
        "selected_days": {0, 1, 2, 3, 4},
        "start_time": "09:00",
        "end_time": "18:00",
        "slot_duration_minutes": 30,
        "buffer_minutes": 15,
        "min_notice_hours": 0,
        "allow_same_day": True,
        "max_days_ahead": 365,
        "timezone": "UTC",
        "show_agenda_in_chat_widget": False,
        "ai_scheduling_chat_enabled": True,
        "ai_scheduling_whatsapp_enabled": True,
    }

    try:
        try:
            settings_res = (
                supabase.table("calendar_settings")
                .select(
                    "calendar_status, selected_days, start_time, end_time, "
                    "slot_duration_minutes, buffer_minutes, min_notice_hours, "
                    "allow_same_day, max_days_ahead, timezone, "
                    "show_agenda_in_chat_widget, ai_scheduling_chat_enabled, ai_scheduling_whatsapp_enabled"
                )
                .eq("client_id", client_id)
                .limit(1)
                .execute()
            )
            settings_data = (settings_res.data or [{}])[0]
        except Exception:
            # Compatibilidad con esquemas legacy sin columnas nuevas.
            legacy_res = (
                supabase.table("calendar_settings")
                .select(
                    "calendar_status, selected_days, start_time, end_time, "
                    "slot_duration_minutes, buffer_minutes, min_notice_hours, "
                    "allow_same_day, max_days_ahead, timezone"
                )
                .eq("client_id", client_id)
                .limit(1)
                .execute()
            )
            settings_data = (legacy_res.data or [{}])[0]
    except Exception:
        settings_data = {}

    try:
        client_res = (
            supabase.table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        client_tz = (client_res.data or [{}])[0].get("timezone")
    except Exception:
        client_tz = None

    profile_tz_name = _get_profile_timezone_name(client_id)
    timezone_name = profile_tz_name or client_tz or settings_data.get("timezone") or default_config["timezone"]
    try:
        ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"

    selected_days = _normalize_selected_days(settings_data.get("selected_days"))

    def _value_or_default(key: str):
        val = settings_data.get(key)
        return default_config[key] if val is None else val

    config = {
        "calendar_status": settings_data.get("calendar_status") or default_config["calendar_status"],
        "selected_days": selected_days,
        "start_time": _value_or_default("start_time"),
        "end_time": _value_or_default("end_time"),
        "slot_duration_minutes": int(_value_or_default("slot_duration_minutes")),
        "buffer_minutes": int(_value_or_default("buffer_minutes")),
        "min_notice_hours": int(_value_or_default("min_notice_hours")),
        "allow_same_day": _as_bool(settings_data.get("allow_same_day"), default_config["allow_same_day"]),
        "max_days_ahead": int(_value_or_default("max_days_ahead")),
        "timezone": timezone_name,
        "show_agenda_in_chat_widget": _as_bool(
            settings_data.get("show_agenda_in_chat_widget", default_config["show_agenda_in_chat_widget"]),
            default_config["show_agenda_in_chat_widget"],
        ),
        "ai_scheduling_chat_enabled": _as_bool(
            settings_data.get("ai_scheduling_chat_enabled", default_config["ai_scheduling_chat_enabled"]),
            default_config["ai_scheduling_chat_enabled"],
        ),
        "ai_scheduling_whatsapp_enabled": _as_bool(
            settings_data.get("ai_scheduling_whatsapp_enabled", default_config["ai_scheduling_whatsapp_enabled"]),
            default_config["ai_scheduling_whatsapp_enabled"],
        ),
    }
    config["max_days_ahead"] = max(1, min(config["max_days_ahead"], 365))
    config["slot_duration_minutes"] = max(5, min(config["slot_duration_minutes"], 240))
    config["buffer_minutes"] = max(0, min(config["buffer_minutes"], 240))
    config["min_notice_hours"] = max(0, min(config["min_notice_hours"], 720))
    return config


def _widget_calendar_booking_enabled_for_plan(client_id: str) -> bool:
    return client_can_use_widget_calendar_booking(client_id)


def _widget_calendar_ai_enabled_for_plan(client_id: str) -> bool:
    return client_can_use_calendar_ai_for_channel(client_id, "chat")


def _normalize_session_uuid(raw_value: str | None) -> uuid.UUID:
    if raw_value:
        try:
            return uuid.UUID(str(raw_value))
        except Exception:
            pass
    return uuid.uuid4()


def _format_slot_iso(iso_value: str | None, timezone_name: str) -> str | None:
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        target_tz = ZoneInfo(timezone_name or "UTC")
        if dt.tzinfo is None:
            # Compatibilidad con registros viejos sin offset:
            # se asumen en hora local del cliente, no en UTC.
            dt = dt.replace(tzinfo=target_tz)
        local_dt = dt.astimezone(target_tz)
        return f"{local_dt.strftime('%Y-%m-%d %H:%M')} ({timezone_name})"
    except Exception:
        return iso_value


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _normalize_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    return re.sub(r"[^\d+]", "", raw)


def _serialize_widget_appointment(appointment: dict, timezone_name: str) -> dict:
    return {
        "id": appointment.get("id"),
        "status": appointment.get("status"),
        "user_name": appointment.get("user_name"),
        "user_email": appointment.get("user_email"),
        "user_phone": appointment.get("user_phone"),
        "appointment_type": appointment.get("appointment_type"),
        "scheduled_time": appointment.get("scheduled_time"),
        "formatted_time": _format_slot_iso(appointment.get("scheduled_time"), timezone_name),
    }


def _find_active_widget_appointment(
    *,
    client_id: str,
    user_email: str | None,
    user_phone: str | None,
) -> dict | None:
    normalized_email = _normalize_email(user_email)
    normalized_phone = _normalize_phone(user_phone)
    now_iso = datetime.now(ZoneInfo("UTC")).isoformat()

    if not normalized_email and not normalized_phone:
        raise HTTPException(status_code=400, detail="Provide at least email or phone")

    upcoming = (
        supabase
        .table("appointments")
        .select("id, status, user_name, user_email, user_phone, scheduled_time, appointment_type")
        .eq("client_id", client_id)
        .in_("status", list(ACTIVE_WIDGET_APPOINTMENT_STATUSES))
        .gte("scheduled_time", now_iso)
        .order("scheduled_time", desc=False)
        .limit(300)
        .execute()
    )
    rows = upcoming.data or []
    if not rows:
        return None

    matching_rows: list[dict] = []
    for row in rows:
        row_email = _normalize_email(row.get("user_email"))
        row_phone = _normalize_phone(row.get("user_phone"))
        matches_email = bool(normalized_email and row_email and row_email == normalized_email)
        matches_phone = bool(normalized_phone and row_phone and row_phone == normalized_phone)

        if matches_email or matches_phone:
            matching_rows.append(row)

    if not matching_rows:
        return None

    matching_rows.sort(key=lambda row: str(row.get("scheduled_time") or ""))
    return matching_rows[0]


def _find_widget_appointment_for_confirmation(
    *,
    client_id: str,
    appointment_id: str,
    user_email: str | None,
    user_phone: str | None,
) -> dict | None:
    normalized_email = _normalize_email(user_email)
    normalized_phone = _normalize_phone(user_phone)

    if not normalized_email and not normalized_phone:
        raise HTTPException(status_code=400, detail="Provide at least email or phone")

    res = (
        supabase
        .table("appointments")
        .select("id, status, user_name, user_email, user_phone, scheduled_time, appointment_type")
        .eq("client_id", client_id)
        .eq("id", appointment_id)
        .in_("status", list(ACTIVE_WIDGET_APPOINTMENT_STATUSES))
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    if not row:
        return None

    row_email = _normalize_email(row.get("user_email"))
    row_phone = _normalize_phone(row.get("user_phone"))
    matches_email = bool(normalized_email and row_email and row_email == normalized_email)
    matches_phone = bool(normalized_phone and row_phone and row_phone == normalized_phone)
    if not (matches_email or matches_phone):
        return None
    return row


def _get_profile_timezone_name(client_id: str) -> str:
    try:
        tz_obj = get_client_timezone(client_id)
        tz_name = getattr(tz_obj, "key", None) or str(tz_obj)
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return "UTC"


@router.get("/widget/calendar/availability")
def get_widget_calendar_availability(
    public_client_id: str = Query(...),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
):
    try:
        client_id = get_client_id_from_public_client_id(public_client_id)
        if not _widget_calendar_booking_enabled_for_plan(client_id):
            return {
                "available": False,
                "timezone": "UTC",
                "slots": [],
                "counts_by_day": {},
                "message": "Calendar booking is not enabled for this plan.",
            }
        config = _get_widget_calendar_config(client_id)

        if config["calendar_status"] != "active":
            return {
                "available": False,
                "timezone": config["timezone"],
                "slots": [],
                "counts_by_day": {},
                "message": "Calendar is inactive for this client.",
            }
        if not config.get("show_agenda_in_chat_widget", False):
            return {
                "available": False,
                "timezone": config["timezone"],
                "slots": [],
                "counts_by_day": {},
                "message": "Calendar is hidden in chat widget for this client.",
            }

        tz = ZoneInfo(config["timezone"])
        now_local = datetime.now(tz).replace(second=0, microsecond=0)
        today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        one_year_ahead = today_local + timedelta(days=365)
        max_range_end = one_year_ahead

        parsed_from = _parse_yyyy_mm_dd(from_date)
        parsed_to = _parse_yyyy_mm_dd(to_date)

        requested_start = parsed_from.replace(tzinfo=tz) if parsed_from else today_local
        requested_end = parsed_to.replace(tzinfo=tz) if parsed_to else min(today_local + timedelta(days=30), max_range_end)
        requested_end = requested_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        range_start = max(requested_start, today_local)
        range_end = min(requested_end, max_range_end.replace(hour=23, minute=59, second=59, microsecond=999999))

        if range_end < range_start:
            return {
                "available": True,
                "timezone": config["timezone"],
                "range": {"start": range_start.isoformat(), "end": range_end.isoformat()},
                "slots": [],
                "counts_by_day": {},
            }

        start_utc = range_start.astimezone(ZoneInfo("UTC"))
        end_utc = range_end.astimezone(ZoneInfo("UTC"))

        booked_res = (
            supabase.table("appointments")
            .select("scheduled_time")
            .eq("client_id", client_id)
            .in_("status", list(WIDGET_CALENDAR_BLOCKING_STATUSES))
            .gte("scheduled_time", start_utc.isoformat())
            .lte("scheduled_time", end_utc.isoformat())
            .execute()
        )

        slot_duration = timedelta(minutes=config["slot_duration_minutes"])
        step = timedelta(minutes=config["slot_duration_minutes"] + config["buffer_minutes"])
        min_notice_dt = now_local + timedelta(hours=config["min_notice_hours"])

        busy_ranges = []
        for row in (booked_res.data or []):
            raw = row.get("scheduled_time")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                local_start = dt.astimezone(tz)
                busy_ranges.append((local_start, local_start + slot_duration))
            except Exception:
                continue

        try:
            google_busy_ranges = _get_google_busy_ranges(client_id, start_utc, end_utc)
        except Exception:
            logging.exception("⚠️ Error fetching Google busy ranges for widget availability")
            google_busy_ranges = []

        for item in google_busy_ranges:
            raw_start = item.get("start")
            raw_end = item.get("end")
            if not raw_start or not raw_end:
                continue
            try:
                busy_start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
                if busy_start.tzinfo is None:
                    busy_start = busy_start.replace(tzinfo=ZoneInfo("UTC"))
                if busy_end.tzinfo is None:
                    busy_end = busy_end.replace(tzinfo=ZoneInfo("UTC"))
                local_start = busy_start.astimezone(tz)
                local_end = busy_end.astimezone(tz)
                if local_end > local_start:
                    busy_ranges.append((local_start, local_end))
            except Exception:
                continue

        try:
            start_h, start_m = [int(v) for v in config["start_time"].split(":", 1)]
            end_h, end_m = [int(v) for v in config["end_time"].split(":", 1)]
        except Exception:
            start_h, start_m = 9, 0
            end_h, end_m = 18, 0
        if (end_h, end_m) <= (start_h, start_m):
            start_h, start_m = 9, 0
            end_h, end_m = 18, 0
        selected_days = config["selected_days"]

        slots = []
        counts_by_day = {}
        current_day = range_start

        while current_day <= range_end:
            if current_day.weekday() in selected_days:
                day_start = current_day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                day_end = current_day.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                slot_pointer = max(day_start, range_start)

                while slot_pointer + slot_duration <= day_end and slot_pointer <= range_end:
                    if slot_pointer < min_notice_dt:
                        slot_pointer += step
                        continue
                    if not config["allow_same_day"] and slot_pointer.date() == now_local.date():
                        slot_pointer += step
                        continue

                    overlaps = any(slot_pointer < busy_end and (slot_pointer + slot_duration) > busy_start for busy_start, busy_end in busy_ranges)
                    if overlaps:
                        slot_pointer += step
                        continue

                    day_key = slot_pointer.strftime("%Y-%m-%d")
                    counts_by_day[day_key] = counts_by_day.get(day_key, 0) + 1
                    slots.append(
                        {
                            "start_iso": slot_pointer.isoformat(),
                            "date": day_key,
                            "time": slot_pointer.strftime("%H:%M"),
                            "display": slot_pointer.strftime("%A %d %B %Y, %H:%M"),
                        }
                    )
                    slot_pointer += step

            current_day = (current_day + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        return {
            "available": True,
            "timezone": config["timezone"],
            "range": {"start": range_start.isoformat(), "end": range_end.isoformat()},
            "slots": slots,
            "counts_by_day": counts_by_day,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error getting widget calendar availability")
        raise HTTPException(status_code=500, detail=f"Calendar availability error: {e}")


@router.get("/widget/calendar/visibility")
def get_widget_calendar_visibility(public_client_id: str = Query(...)):
    try:
        client_id = get_client_id_from_public_client_id(public_client_id)
        config = _get_widget_calendar_config(client_id)
        widget_booking_feature_enabled = _widget_calendar_booking_enabled_for_plan(client_id)
        chat_ai_feature_enabled = _widget_calendar_ai_enabled_for_plan(client_id)
        return {
            "show_agenda_in_chat_widget": bool(
                widget_booking_feature_enabled and config.get("show_agenda_in_chat_widget", False)
            ),
            "calendar_status": config.get("calendar_status") or "inactive",
            "ai_scheduling_chat_enabled": bool(
                chat_ai_feature_enabled and config.get("ai_scheduling_chat_enabled", True)
            ),
            "widget_calendar_booking_enabled": bool(widget_booking_feature_enabled),
            "calendar_ai_chat_feature_enabled": bool(chat_ai_feature_enabled),
            "timezone": config.get("timezone") or "UTC",
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error getting widget calendar visibility")
        raise HTTPException(status_code=500, detail=f"Calendar visibility error: {e}")


@router.post("/widget/calendar/book")
async def book_widget_calendar(payload: WidgetBookRequest):
    try:
        client_id = get_client_id_from_public_client_id(payload.public_client_id)
        if not _widget_calendar_booking_enabled_for_plan(client_id):
            raise HTTPException(status_code=403, detail="Calendar booking is not enabled for this plan.")
        config = _get_widget_calendar_config(client_id)
        if config["calendar_status"] != "active":
            raise HTTPException(status_code=403, detail="Calendar booking is disabled for this client.")
        if not config.get("show_agenda_in_chat_widget", False):
            raise HTTPException(status_code=403, detail="Calendar booking is hidden in chat widget for this client.")
        user_name = (payload.user_name or "").strip()
        user_email = (payload.user_email or "").strip() or None
        user_phone = (payload.user_phone or "").strip() or None

        if not user_name:
            raise HTTPException(status_code=400, detail="user_name is required")
        if not user_email and not user_phone:
            raise HTTPException(status_code=400, detail="Provide at least one contact method (email or phone)")

        try:
            scheduled_dt = datetime.fromisoformat(str(payload.scheduled_time).replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="scheduled_time must be a valid ISO datetime")

        now_utc = datetime.now(ZoneInfo("UTC"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            scheduled_dt = scheduled_dt.astimezone(ZoneInfo("UTC"))

        if scheduled_dt < now_utc:
            raise HTTPException(status_code=400, detail="Cannot book past times")
        if scheduled_dt > (now_utc + timedelta(days=365)):
            raise HTTPException(status_code=400, detail="Cannot book beyond one year")

        conflict_start = scheduled_dt.isoformat()
        conflict_end = (scheduled_dt + timedelta(minutes=1)).isoformat()
        conflict_res = (
            supabase.table("appointments")
            .select("id")
            .eq("client_id", client_id)
            .in_("status", list(WIDGET_CALENDAR_BLOCKING_STATUSES))
            .gte("scheduled_time", conflict_start)
            .lt("scheduled_time", conflict_end)
            .limit(1)
            .execute()
        )
        if conflict_res.data:
            raise HTTPException(status_code=409, detail="This time is no longer available")

        create_payload = CreateAppointmentPayload(
            client_id=uuid.UUID(client_id),
            session_id=_normalize_session_uuid(payload.session_id),
            scheduled_time=scheduled_dt,
            user_name=user_name,
            user_email=user_email,
            user_phone=user_phone,
            appointment_type="AI Assistant - Chat Widget",
            channel="widget",
            send_reminders=False,
            replace_existing=bool(payload.replace_existing),
        )

        result = await create_appointment_route(create_payload)
        if result and result.get("calendar_inactive"):
            raise HTTPException(status_code=403, detail=result.get("message") or "Calendar booking is disabled.")
        if result and result.get("invalid_time"):
            raise HTTPException(status_code=400, detail=result.get("message") or "Invalid booking time")

        if result and result.get("overlap_conflict"):
            existing = result.get("existing_appointment") or {}
            config = _get_widget_calendar_config(client_id)
            existing["formatted_time"] = _format_slot_iso(existing.get("scheduled_time"), config.get("timezone", "UTC"))
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "overlap_conflict": True,
                    "message": result.get("message") or "This time is no longer available.",
                    "existing_appointment": existing,
                    "timezone": config.get("timezone", "UTC"),
                },
            )

        if result and result.get("duplicate_active"):
            existing = result.get("existing_appointment") or {}
            config = _get_widget_calendar_config(client_id)
            existing["formatted_time"] = _format_slot_iso(existing.get("scheduled_time"), config.get("timezone", "UTC"))
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "duplicate_active": True,
                    "message": "Active appointment already exists for this contact.",
                    "existing_appointment": existing,
                    "timezone": config.get("timezone", "UTC"),
                },
            )

        if not result or not result.get("success"):
            raise HTTPException(status_code=500, detail="Unable to create appointment")

        return {
            "success": True,
            "appointment_id": result.get("appointment_id"),
            "scheduled_time": result.get("scheduled_time"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error booking widget calendar")
        raise HTTPException(status_code=500, detail=f"Widget booking error: {e}")


@router.post("/widget/calendar/cancel/lookup")
async def lookup_widget_calendar_cancellation(payload: WidgetCancelLookupRequest, request: Request):
    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="widget_calendar_cancel_lookup",
            key=f"{payload.public_client_id}:{request_ip}",
            limit=30,
            window_seconds=60,
        )

        client_id = get_client_id_from_public_client_id(payload.public_client_id)
        config = _get_widget_calendar_config(client_id)
        appointment = _find_active_widget_appointment(
            client_id=client_id,
            user_email=payload.user_email,
            user_phone=payload.user_phone,
        )

        if not appointment:
            return {
                "success": True,
                "found": False,
                "message": "No encontramos una cita activa con esos datos.",
            }

        return {
            "success": True,
            "found": True,
            "timezone": config.get("timezone", "UTC"),
            "appointment": _serialize_widget_appointment(appointment, config.get("timezone", "UTC")),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error looking up widget cancellation")
        raise HTTPException(status_code=500, detail=f"Widget cancellation lookup error: {e}")


@router.post("/widget/calendar/cancel/confirm")
async def confirm_widget_calendar_cancellation(payload: WidgetCancelConfirmRequest, request: Request):
    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="widget_calendar_cancel_confirm",
            key=f"{payload.public_client_id}:{request_ip}",
            limit=20,
            window_seconds=60,
        )

        client_id = get_client_id_from_public_client_id(payload.public_client_id)
        config = _get_widget_calendar_config(client_id)
        appointment = _find_widget_appointment_for_confirmation(
            client_id=client_id,
            appointment_id=str(payload.appointment_id or "").strip(),
            user_email=payload.user_email,
            user_phone=payload.user_phone,
        )

        if not appointment:
            raise HTTPException(status_code=404, detail="No active appointment found for provided contact.")

        appointment_id = str(appointment.get("id") or "").strip()
        if not appointment_id:
            raise HTTPException(status_code=404, detail="Appointment id not found.")

        already_cancelled, reminders_cancelled = await _cancel_appointment_record(
            appointment=appointment,
            client_id=client_id,
            appointment_id=appointment_id,
            usage_channel="widget",
            usage_action="cancelled_from_widget",
        )

        return {
            "success": True,
            "already_cancelled": bool(already_cancelled),
            "reminders_cancelled": int(reminders_cancelled or 0),
            "timezone": config.get("timezone", "UTC"),
            "appointment": _serialize_widget_appointment(appointment, config.get("timezone", "UTC")),
            "message": (
                "La cita ya estaba cancelada."
                if already_cancelled
                else "Tu cita ha sido cancelada."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error confirming widget cancellation")
        raise HTTPException(status_code=500, detail=f"Widget cancellation confirm error: {e}")


# 🔹 Main chat endpoint
@router.post("/chat")
async def chat_widget(request: Request):
    try:
        print("📥 Incoming request to /chat")

        body = await request.json()
        print(
            "📦 Received /chat body metadata:",
            {
                "keys": list(body.keys()),
                "has_message": bool(body.get("message")),
                "message_length": len(str(body.get("message") or "")),
            },
        )

        required_fields = ["public_client_id", "session_id", "message"]
        if not all(field in body for field in required_fields):
            raise HTTPException(status_code=400, detail="Missing required fields: public_client_id, session_id, message")

        public_client_id = body["public_client_id"]
        session_id = body["session_id"]
        message = body["message"]
        channel = body.get("channel", "chat")
        request_ip = get_request_ip(request)

        enforce_rate_limit(
            scope="chat_widget_ip",
            key=f"{public_client_id}:{request_ip}",
            limit=120,
            window_seconds=60,
        )
        enforce_rate_limit(
            scope="chat_widget_session",
            key=f"{public_client_id}:{session_id}",
            limit=40,
            window_seconds=60,
        )

        print(
            f"💬 [{channel}] Message received "
            f"(public_client_id={public_client_id}, session_id={session_id}, message_length={len(message)})"
        )

        # Get actual client_id
        client_id = get_client_id_from_public_client_id(public_client_id)
        print(f"✅ client_id resolved: {client_id}")

        # Validate plan usage
        check_and_increment_usage(client_id, usage_type="messages_used")

        # 🧩 Obtener límite dinámico de mensajes desde client_settings
        MAX_MESSAGES_PER_SESSION = get_max_messages_per_session(client_id)

        # Count messages for this session
        ten_minutes_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        history_count_res = (
            supabase.table("history")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .gte("created_at", ten_minutes_ago)
            .execute()
        )
        total_messages = len(history_count_res.data or [])
        print(f"💬 Total messages in session {session_id}: {total_messages} / {MAX_MESSAGES_PER_SESSION * 2}")

        # 🔒 Session limit
        if total_messages >= MAX_MESSAGES_PER_SESSION * 2:  # user+assistant pairs
            user_lang = detect_language(message)
            print(f"🌍 Detected language: {user_lang}")

            limit_messages = {
                "en":("Ahora mismo no puedo responder nuevas preguntas. Intenta nuevamente en unos minutos para continuar la conversación."),
                "es":("I can’t answer new questions right now. Please try again in a few minutes to continue the conversation."),
            }


            limit_message = limit_messages.get(user_lang, limit_messages["en"])
            return {"answer": limit_message, "session_id": session_id, "limit_reached": True}

        # Retrieve recent history
        history_res = (
            supabase.table("history")
            .select("role, content")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(6)
            .execute()
        )
        history_messages = [
            {"role": h["role"], "content": h["content"]}
            for h in (history_res.data or [])
        ]

        # Add current message
        history_messages.append({"role": "user", "content": message})

        # 🧠 INTENT ROUTER — procesa citas, agenda, RAG u otros
        print("🤖 Routing through intent system...")
        answer = await process_user_message(
            client_id,
            session_id,
            message,
            channel,
            provider="widget",
            return_metadata=True,
        )

        print("✅ Generated answer:", answer)
        if isinstance(answer, dict):
            response_payload = {
                "answer": str(answer.get("answer") or ""),
                "session_id": session_id,
                "confidence_score": answer.get("confidence_score"),
                "handoff_recommended": bool(answer.get("handoff_recommended")),
                "human_intervention_recommended": bool(answer.get("human_intervention_recommended")),
                "needs_human": bool(answer.get("needs_human")),
                "handoff_reason": answer.get("handoff_reason"),
                "confidence_reason": answer.get("confidence_reason"),
            }
            return response_payload

        return {"answer": answer, "session_id": session_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception("❌ Unexpected error in /chat")
        raise HTTPException(status_code=500, detail="Error processing the message.")


# 🔹 Serve widget HTML
@router.get("/chat-widget", response_class=HTMLResponse)
def serve_chat_widget(public_client_id: str):
    try:
        client_id = get_client_id_from_public_client_id(public_client_id)
        html_path = Path("dist/chat-widget.html")
        if not html_path.exists():
            raise HTTPException(status_code=500, detail="Widget HTML file not found")
        return HTMLResponse(content=html_path.read_text(), status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception("❌ Unexpected error in /chat-widget")
        raise HTTPException(status_code=500, detail="Error loading widget.")
