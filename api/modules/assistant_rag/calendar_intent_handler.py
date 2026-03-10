# =====================================================
# 📅 calendar_intent_handler.py — Production-ready LLM-only handler
# =====================================================
import json
import logging
import re
import uuid
import unicodedata
from datetime import datetime, timedelta, time as dtime, timezone
from api.modules.assistant_rag.prompts.calendar_prompt import get_calendar_prompt
from api.modules.assistant_rag.llm import openai_chat
from api.modules.assistant_rag.supabase_client import supabase
from zoneinfo import ZoneInfo
from api.modules.calendar.get_booked_slots import get_booked_slots
from api.appointments.create_appointment import (
    CreateAppointmentPayload,
    create_appointment as create_appointment_route,
)
from api.utils.babel_compat import format_datetime






logger = logging.getLogger("calendar_intent_handler")

WEEKDAYS_ES = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
WEEKDAYS_EN = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
MONTHS_ES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
MONTHS_EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}

ENUM_PREFIX_RE = re.compile(r"^\s*\d+\s*[\.\)]\s*")
TIME_RE = re.compile(r"(?<!\d\.)\b(?!\d+\s*\.)" r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.I)
RANGE_RE = re.compile(r"\b(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\b", re.I)

YES_TOKENS = {"si", "sí", "yes", "yep", "sure", "ok", "okay", "vale", "confirmo", "confirm", "proceed"}
NO_TOKENS = {"no", "nop", "nope", "cancel", "cancelar", "stop"}
E164_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")



def _is_valid_email(email: str) -> bool:
    """
    Valida emails reales, evitando casos como:
    - doble punto
    - dominios inválidos
    - sin TLD
    - espacios
    - rarezas como test@test, test@.com
    """
    if not email:
        return False

    email = email.strip()

    pattern = re.compile(
        r"^(?!.*\.\.)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$",
        re.IGNORECASE,
    )

    return bool(pattern.match(email))


def _detect_lang_signal(text: str) -> str | None:
    t = (text or "").lower()
    es_signals = {
        "hola", "quiero", "agendar", "cita", "correo", "teléfono", "telefono",
        "mañana", "viernes", "lunes", "martes", "miércoles", "miercoles", "jueves",
        "confirmo", "sí", "si", "a las"
    }
    en_signals = {
        "hello", "book", "appointment", "email", "phone", "tomorrow",
        "friday", "monday", "tuesday", "wednesday", "thursday", "confirm"
    }
    if any(c in t for c in "áéíóúñ¿¡") or any(w in t for w in es_signals):
        return "es"
    if any(w in t for w in en_signals):
        return "en"
    return None


def _format_slot_for_lang(iso_str: str, tz_name: str, lang: str) -> str:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    target_tz = ZoneInfo(tz_name or "UTC")
    if dt.tzinfo is None:
        # Compatibilidad con citas históricas guardadas sin offset.
        dt = dt.replace(tzinfo=target_tz)
    local_dt = dt.astimezone(target_tz)
    return format_datetime(
        local_dt,
        "EEEE dd 'de' MMMM yyyy, HH:mm" if lang == "es" else "EEEE, MMMM dd yyyy, HH:mm",
        locale="es_MX" if lang == "es" else "en_US",
    )


def _pick_display_slots(slots: list[dict], tz_name: str, *, limit: int = 9, max_per_day: int = 3) -> list[dict]:
    if limit <= 0:
        return []
    tz = ZoneInfo(tz_name or "UTC")
    parsed: list[tuple[dict, datetime, str]] = []
    for slot in slots or []:
        iso = str((slot or {}).get("start_iso") or "").strip()
        if not iso:
            continue
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            local_dt = dt.astimezone(tz)
            parsed.append((slot, local_dt, local_dt.strftime("%Y-%m-%d")))
        except Exception:
            continue

    parsed.sort(key=lambda item: item[1])

    picked: list[dict] = []
    overflow: list[dict] = []
    per_day_count: dict[str, int] = {}

    for slot, _dt, day_key in parsed:
        if len(picked) >= limit:
            break
        day_total = per_day_count.get(day_key, 0)
        if day_total < max_per_day:
            picked.append(slot)
            per_day_count[day_key] = day_total + 1
        else:
            overflow.append(slot)

    if len(picked) < limit:
        for slot in overflow:
            if len(picked) >= limit:
                break
            picked.append(slot)

    return picked


def _format_slot_list_for_lang(slots: list[dict], tz_name: str, lang: str, limit: int = 9) -> str:
    out = []
    for slot in _pick_display_slots(slots or [], tz_name, limit=limit):
        iso = slot.get("start_iso")
        if not iso:
            continue
        out.append(f"- {_format_slot_for_lang(iso, tz_name, lang)}")
    return "\n".join(out)


def _filter_slots_for_date(slots: list[dict], tz_name: str, date_iso: str) -> list[dict]:
    target_date = str(date_iso or "").strip()
    if not target_date:
        return slots or []
    tz = ZoneInfo(tz_name or "UTC")
    filtered: list[dict] = []
    for slot in slots or []:
        iso = str((slot or {}).get("start_iso") or "").strip()
        if not iso:
            continue
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            local_dt = dt.astimezone(tz)
            if local_dt.strftime("%Y-%m-%d") == target_date:
                filtered.append(slot)
        except Exception:
            continue
    return filtered


def _normalize_phone_for_booking(phone_value: str | None, session_id: str, channel: str) -> str | None:
    raw = str(phone_value or "").strip()
    if not raw:
        return None

    compact = re.sub(r"[^\d+]", "", raw)
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"

    if compact.startswith("+"):
        digits = re.sub(r"\D", "", compact)
        candidate = f"+{digits}"
        return candidate if E164_PHONE_RE.fullmatch(candidate) else compact

    digits = re.sub(r"\D", "", compact)
    if not digits:
        return raw

    channel_name = (channel or "").lower()
    session_digits = ""
    if "whatsapp" in channel_name:
        raw_session = str(session_id or "").strip()
        if raw_session.startswith("whatsapp-"):
            session_digits = re.sub(r"\D", "", raw_session[len("whatsapp-") :])
            if session_digits.startswith("521") and len(session_digits) > 3:
                session_digits = f"52{session_digits[3:]}"
            if session_digits and session_digits.endswith(digits):
                candidate = f"+{session_digits}"
                if E164_PHONE_RE.fullmatch(candidate):
                    return candidate
            if session_digits and len(digits) == 10 and len(session_digits) > 10:
                country_prefix = session_digits[:-10]
                candidate = f"+{country_prefix}{digits}"
                if E164_PHONE_RE.fullmatch(candidate):
                    return candidate

    if len(digits) >= 11:
        candidate = f"+{digits}"
        if E164_PHONE_RE.fullmatch(candidate):
            return candidate

    return raw


def _infer_whatsapp_phone_from_session(session_id: str, channel: str) -> str | None:
    if "whatsapp" not in str(channel or "").lower():
        return None
    raw_session = str(session_id or "").strip()
    if raw_session.startswith("whatsapp-"):
        raw_session = raw_session[len("whatsapp-") :]
    candidate = _normalize_phone_for_booking(raw_session, session_id, channel)
    if not candidate:
        return None
    digits = re.sub(r"\D", "", candidate)
    normalized = f"+{digits}" if digits else ""
    if normalized and E164_PHONE_RE.fullmatch(normalized):
        return normalized
    return None


def _coerce_dict(val):
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}


def _is_yes(msg: str) -> bool:
    s = msg.strip().lower()

    # Palabras muy claras de confirmación
    strong_yes = [
        "si", "sí", "yes", "yep", "sure", "ok", "okay", "vale",
        "confirmo", "confirmar", "confirmada", "confirmada", 
        "proceed", "procede"
    ]

    for kw in strong_yes:
        if kw in s:
            return True

    # Evitar palabras de intent como "agendar", "book", "schedule"
    intent_words = ["agendar", "book", "schedule", "reservar"]
    if any(w in s for w in intent_words):
        return False

    return False




def _is_no(msg: str) -> bool:
    s = msg.strip().lower()
    no_keywords = ["no", "nop", "nope", "cancel", "cancelar", "stop", "rechazar"]
    return any(kw in s for kw in no_keywords)



def _next_weekday(base: datetime, target_wd: int) -> datetime:
    delta = (target_wd - base.weekday()) % 7
    return base + timedelta(days=delta or 7)


def _normalize_time_str(hhmm_ampm: str) -> str:
    s = hhmm_ampm.strip().lower().replace(" ", "")
    ampm = None
    if s.endswith("am") or s.endswith("pm"):
        ampm = s[-2:]
        s = s[:-2]
    hh, mm = (s.split(":", 1) + ["00"])[:2] if ":" in s else (s, "00")
    h = int(hh)
    m = int(re.sub(r"\D", "", mm) or 0)
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"

def _safe_datetime(dt_str: str) -> str | None:
    """
    Verifica que un datetime ISO sea válido.
    Evita errores como horas 24, 25, 99 o minutos inválidos.
    Retorna el mismo string si es válido, o None si no lo es.
    """
    try:
        # Reemplazo de Z por ISO normal
        datetime.fromisoformat(dt_str.replace("Z", ""))
        return dt_str
    except Exception:
        logger.warning(f"⚠️ Invalid datetime detected and ignored: {dt_str}")
        return None



def _resolve_date_token(text: str) -> str | None:
    s = text.lower()
    now = datetime.now()

    # ===============================
    # 1. Expresiones absolutas simples (hoy, mañana...)
    # ===============================
    if "hoy" in s or "today" in s:
        return now.strftime("%Y-%m-%d")

    if "pasado mañana" in s or "day after tomorrow" in s:
        return (now + timedelta(days=2)).strftime("%Y-%m-%d")

    if "mañana" in s or "manana" in s or "tomorrow" in s:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    # ===============================
    # 2. Expresiones relativas por semanas
    # ===============================
    # “en dos semanas”, “en 3 semanas”, “in two weeks”, “in 3 weeks”
    m = re.search(r"\ben\s+(\d+)\s+seman", s)
    if m:
        n = int(m.group(1))
        return (now + timedelta(days=7*n)).strftime("%Y-%m-%d")

    m = re.search(r"\bin\s+(\d+)\s+week", s)
    if m:
        n = int(m.group(1))
        return (now + timedelta(days=7*n)).strftime("%Y-%m-%d")

    # ===============================
    # 3. Expresiones como “en 3 días”, “in 2 days”
    # ===============================
    m = re.search(r"\ben\s+(\d+)\s+d[ií]as", s)
    if m:
        return (now + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

    m = re.search(r"\bin\s+(\d+)\s+day", s)
    if m:
        return (now + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

    # ===============================
    # 4. Detección de modificadores tipo Calendly
    # ===============================
    modifiers_next = [
        "siguiente", "próximo", "proximo", "que viene", 
        "upcoming", "next", "following"
    ]
    modifiers_this = [
        "este", "esta", "this"
    ]

    # ===============================
    # 5. Días de la semana (ES)
    # ===============================
    for wd, idx in WEEKDAYS_ES.items():
        if wd in s:
            base = _next_weekday(now, idx)

            # “el siguiente lunes” → +7 días extra
            if any(m in s for m in modifiers_next):
                base += timedelta(days=7)

            # “este lunes” → lunes de esta semana (solo si todavía no pasó)
            if any(m in s for m in modifiers_this):
                if now.weekday() <= idx:
                    base = now + timedelta(days=(idx - now.weekday()))
            return base.strftime("%Y-%m-%d")

    # ===============================
    # 6. Días de la semana (EN)
    # ===============================
    for wd, idx in WEEKDAYS_EN.items():
        if wd in s:
            base = _next_weekday(now, idx)

            if any(m in s for m in modifiers_next):
                base += timedelta(days=7)

            if any(m in s for m in modifiers_this):
                if now.weekday() <= idx:
                    base = now + timedelta(days=(idx - now.weekday()))

            return base.strftime("%Y-%m-%d")

    # ===============================
    # 7. Fechas explícitas tipo “14 de noviembre”
    # ===============================
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\b", s)
    if m:
        d = int(m.group(1))
        mo = MONTHS_ES.get(m.group(2).lower())
        if mo:
            try:
                return datetime(now.year, mo, d).strftime("%Y-%m-%d")
            except:
                return None

    # ===============================
    # 8. Fechas explícitas inglés: “November 14”
    # ===============================
    m = re.search(r"\b([a-z]+)\s+(\d{1,2})\b", s)
    if m and m.group(1).lower() in MONTHS_EN:
        mo = MONTHS_EN[m.group(1).lower()]
        d = int(m.group(2))
        try:
            return datetime(now.year, mo, d).strftime("%Y-%m-%d")
        except:
            return None

    # ===============================
    # 9. Estilo “14th of November”
    # ===============================
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+([a-z]+)\b", s)
    if m and m.group(2).lower() in MONTHS_EN:
        d = int(m.group(1))
        mo = MONTHS_EN[m.group(2).lower()]
        try:
            return datetime(now.year, mo, d).strftime("%Y-%m-%d")
        except:
            return None

    return None


def _extract_times_from_text(text: str) -> list[str]:
    text = text.lower().strip()

    # 0️⃣ Clean fake "21:" tokens coming from list formatting
    text = re.sub(r"\b(\d{1,2}):\s*(?=,|$)", "", text)

    # 1️⃣ Time ranges "10:00-11:00"
    ranges = RANGE_RE.findall(text)
    if ranges:
        return [r[0] for r in ranges]

    # 2️⃣ HH:MM with optional AM/PM
    matches = re.findall(
        r"\b(1[0-2]|0?[1-9]|1[3-9]|2[0-3]):([0-5][0-9])\s*(am|pm)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        result = []
        for hh, mm, ampm in matches:
            # Prevent 24–99 hours from entering
            if int(hh) > 23:
                continue
            t = f"{hh}:{mm}"
            if ampm:
                t += ampm
            result.append(t)
        return result

    # 3️⃣ "9am", "11pm"
    relaxed = re.findall(
        r"\b(1[0-2]|0?[1-9])\s*(am|pm)\b",
        text,
        flags=re.IGNORECASE,
    )
    if relaxed:
        return [f"{hh}{ampm}" for hh, ampm in relaxed]

    # 4️⃣ "a las 11" / "at 11" (sin minutos ni am/pm)
    plain_hour = re.search(r"(?:a\s+las|at)\s*(\d{1,2})\b", text, flags=re.IGNORECASE)
    if plain_hour:
        h = int(plain_hour.group(1))
        if 0 <= h <= 23:
            return [f"{h:02d}:00"]

    return []



def _looks_like_name(message: str) -> bool:
    s = message.strip()
    low = s.lower()

    # ❗ Nuevo: evitar que confirmaciones o rechazos sean marcados como nombre
    if _is_yes(low) or _is_no(low):
        return False

    # Ya existente:
    if any(ch.isdigit() for ch in s) or "@" in low:
        return False
    if low in YES_TOKENS or low in NO_TOKENS:
        return False

    forbidden = [
        "horario", "disponible", "agendar", "reservar", "cita",
        "llamada", "dame", "book", "schedule", "available",
        "options", "opciones", "number", "número", "numero",
        "option", "confirm", "confirmar", "confirmo", "confirmada"
    ]
    if any(w in low for w in forbidden):
        return False

    if not re.search(r"[a-záéíóúñ]", low):
        return False

    return len(s.split()) >= 2



def _extract_selection_index(msg: str) -> int | None:
    """
    Solo acepta selección clara de opciones:
    - "option 1"
    - "opcion 2"
    - "#3"
    - "3." o "3)"
    - Mensaje que solo contenga un número (ej. "2")
    NO acepta números dentro de emails, teléfonos o textos largos.
    """
    low = msg.lower().strip()

    # Caso donde el mensaje es únicamente un número
    if re.fullmatch(r"[1-9]|1[0-9]|2[0-9]", low):
        return int(low) - 1

    # Opciones explícitas tipo `option 3`, `opción 2`, `#4`
    m = re.search(r"(option|opcion|opción|number|número|numero|#)\s*(\d{1,2})", low)
    if m:
        return int(m.group(2)) - 1

    return None



def _load_settings(client_id: str) -> dict | None:
    try:
        res = supabase.table("calendar_settings").select("*").eq("client_id", client_id).limit(1).execute()
        settings = res.data[0] if res and res.data else {}

        # Prioriza timezone de My Profile (client_settings.timezone)
        profile_res = (
            supabase.table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        profile_tz = (profile_res.data or [{}])[0].get("timezone")
        if profile_tz:
            settings["timezone"] = profile_tz

        return settings or None
    except Exception as e:
        logger.warning(f"⚠️ Could not load calendar_settings: {e}")
        return None


def _validate_slot(settings: dict, iso_str: str) -> tuple[bool, str | None]:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", ""))
    except Exception:
        return False, "Fecha/hora inválida."

    # -----------------------------------------------------------
    # 🔧 FIX: comparar aware vs aware (timezone correcto)
    # -----------------------------------------------------------
    if dt.tzinfo is not None:
        now = datetime.now(dt.tzinfo)   # aware (mismo timezone del cliente)
    else:
        now = datetime.now()            # naive fallback

    min_h = int(settings.get("min_notice_hours") or 0)
    if dt < now + timedelta(hours=min_h):
        return False, f"Debe respetar aviso mínimo de {min_h} horas."

    # -----------------------------------------------------------
    # Horario laboral dentro del timezone del cliente
    # -----------------------------------------------------------
    start = settings.get("start_time")
    end = settings.get("end_time")
    if start and end:
        s_h, s_m = map(int, start.split(":"))
        e_h, e_m = map(int, end.split(":"))

        # dt.hour y dt.minute ya están en TZ del cliente
        if not (dtime(s_h, s_m) <= dtime(dt.hour, dt.minute) <= dtime(e_h, e_m)):
            return False, f"Fuera del horario laboral ({start}–{end})."

    return True, None


def _normalize_session_uuid(client_id: str, session_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(session_id))
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"{client_id}:{session_id}")


def _appointment_label_for_channel(channel: str) -> str:
    c = (channel or "").lower()
    if "whatsapp" in c:
        return "AI Assistant - WhatsApp"
    if "widget" in c:
        return "AI Assistant - Chat Widget"
    return "AI Assistant - Chat"


async def _book_appointment(client_id: str, session_id: str, collected: dict, channel: str, replace_existing: bool = False) -> dict:
    try:
        scheduled_time = datetime.fromisoformat(
            str(collected.get("scheduled_time")).replace("Z", "+00:00")
        )

        normalized_phone = _normalize_phone_for_booking(collected.get("user_phone"), session_id, channel)

        payload = CreateAppointmentPayload(
            client_id=uuid.UUID(client_id),
            session_id=_normalize_session_uuid(client_id, session_id),
            scheduled_time=scheduled_time,
            user_name=collected.get("user_name") or "Cliente",
            user_email=collected.get("user_email"),
            user_phone=normalized_phone,
            appointment_type=_appointment_label_for_channel(channel),
            channel=channel or "chat",
            send_reminders=False,
            replace_existing=replace_existing,
        )

        result = await create_appointment_route(payload)
        if result and result.get("duplicate_active"):
            return {
                "ok": False,
                "duplicate_active": True,
                "existing_appointment": result.get("existing_appointment") or {},
            }
        booking_ok = bool(result and result.get("success"))
        error_message = str((result or {}).get("message") or "").strip()
        invalid_phone = bool((result or {}).get("invalid_phone"))
        if (not invalid_phone) and error_message and "phone must include country code" in error_message.lower():
            invalid_phone = True
        return {
            "ok": booking_ok,
            "message": error_message,
            "invalid_phone": invalid_phone,
            "invalid_time": bool((result or {}).get("invalid_time")),
            "overlap_conflict": bool((result or {}).get("overlap_conflict")),
        }
    except Exception as e:
        logger.error(f"❌ Error creating appointment via appointments module: {e}")
        return {"ok": False, "error": str(e)}


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from api.modules.assistant_rag.supabase_client import supabase
import logging

logger = logging.getLogger("calendar_intent_handler")


def _get_booked_slots(client_id: str, start_date: datetime, end_date: datetime):
    """
    Obtiene todas las citas ocupadas de Supabase dentro de un rango de fechas.
    Retorna una lista de datetime (timezone-aware), listos para comparación
    en _generate_available_slots().
    """
    try:
        logger.info(
            f"🔍 Fetching booked slots for {client_id} between "
            f"{start_date.isoformat()} and {end_date.isoformat()}"
        )

        res = (
            supabase.table("appointments")
            .select("scheduled_time")
            .eq("client_id", client_id)
            .gte("scheduled_time", start_date.isoformat())
            .lte("scheduled_time", end_date.isoformat())
            .execute()
        )

        if not res or not res.data:
            return []

        booked = []
        for item in res.data:
            iso_str = item["scheduled_time"]

            try:
                # Convert ISO from DB to datetime
                dt = datetime.fromisoformat(iso_str)

                # Ensure timezone aware (DB may return UTC or naive)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))

                booked.append(dt)

            except Exception as parse_err:
                logger.warning(f"⚠️ Could not parse stored datetime: {iso_str} ({parse_err})")

        logger.info(f"⛔ Found {len(booked)} booked slots in Supabase")
        return booked

    except Exception as e:
        logger.error(f"❌ Error fetching booked slots: {e}")
        return []


def _generate_available_slots(settings, client_id):
    """
    Genera todos los horarios disponibles basados en:
    - calendario del cliente
    - citas ya ocupadas (Supabase)
    - horario laboral
    - slot duration
    - buffer
    - min notice
    - max days ahead
    """
    tz = ZoneInfo(settings["timezone"])
    now = datetime.now(tz)

    max_days = settings["max_days_ahead"]
    slot_duration = settings["slot_duration_minutes"]
    buffer = settings["buffer_minutes"]
    min_notice = settings["min_notice_hours"]
    allow_same_day = settings["allow_same_day"]

    start_h, start_m = map(int, settings["start_time"].split(":"))
    end_h, end_m = map(int, settings["end_time"].split(":"))

    # selected days → ["mon","tue","wed"]
    selected_days = [d.lower()[:3] for d in settings["selected_days"]]

    # 1️⃣ Rango de fechas
    date_end = now + timedelta(days=max_days)

    # 2️⃣ Obtener citas ocupadas de Supabase
    booked_raw = _get_booked_slots(client_id, now, date_end)

    # Convertir a timezone del cliente
    booked = []
    for b in booked_raw:
        if b.tzinfo is None:
            b = b.replace(tzinfo=ZoneInfo("UTC"))
        booked.append(b.astimezone(tz))

    free_slots = []

    # Función para detectar solapamientos reales
    def _overlap(slot_start):
        slot_end = slot_start + timedelta(minutes=slot_duration)

        for b in booked:
            b_end = b + timedelta(minutes=slot_duration)

            if (slot_start < b_end) and (slot_end > b):
                return True

        return False

    # 3️⃣ Día por día
    day = now
    while day <= date_end:

        if day.strftime("%a").lower()[:3] in selected_days:

            day_start = day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            day_end = day.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

            slot = day_start
            while slot + timedelta(minutes=slot_duration) <= day_end:

                # ⛔️ Aviso mínimo
                if slot < now + timedelta(hours=min_notice):
                    slot += timedelta(minutes=slot_duration + buffer)
                    continue

                # ⛔️ No permitir mismo día si está desactivado
                if not allow_same_day and slot.date() == now.date():
                    slot += timedelta(minutes=slot_duration + buffer)
                    continue

                # ⛔️ Revisar si se empalma con citas reservadas
                if _overlap(slot):
                    slot += timedelta(minutes=slot_duration + buffer)
                    continue

                # Slot válido
                free_slots.append({
                    "start_iso": slot.isoformat(),
                    "readable": slot.strftime("%Y-%m-%d %H:%M")
                })

                slot += timedelta(minutes=slot_duration + buffer)

        day += timedelta(days=1)

    return free_slots




def _extract_fields(message: str, state: dict, settings: dict) -> dict:
    msg = message.strip()
    low = msg.lower()
    EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,}")

    out = {}

    # -----------------------------------------------------------
    # 📧 Email
    # -----------------------------------------------------------
    # Captura emails buenos y malos — luego se validan aparte
    EMAIL_LOOSE_RE = re.compile(r"[^\s]+@[^\s]+", re.I)

    m = EMAIL_LOOSE_RE.search(msg)
    if m:
        out["user_email"] = m.group(0).strip()


    # -----------------------------------------------------------
    # 📱 Phone
    # -----------------------------------------------------------
    m = PHONE_RE.search(msg)
    if m:
        out["user_phone"] = re.sub(r"\s+", "", m.group(0))

    # -----------------------------------------------------------
    # 🧑 Name
    # -----------------------------------------------------------
    if _looks_like_name(msg):
        out["user_name"] = msg.title()

    # -----------------------------------------------------------
    # 🔢 Selected option from proposed slots
    # -----------------------------------------------------------
    if state.get("proposed_slots"):
        idx = _extract_selection_index(msg)
        if idx is not None and 0 <= idx < len(state["proposed_slots"]):
            out["scheduled_time"] = state["proposed_slots"][idx]["start_iso"]

    # -----------------------------------------------------------
    # 📅 Date extracted
    # -----------------------------------------------------------
    date_iso = _resolve_date_token(low)
    if date_iso:
        out["scheduled_date_hint"] = date_iso
        # Mantener pista de fecha aunque todavía no llegue la hora
        # (resiliencia ante pérdida de conversation_state entre turnos).
        state["last_date_hint"] = date_iso

    # -----------------------------------------------------------
    # ⏰ Time extracted
    # -----------------------------------------------------------
    times = _extract_times_from_text(msg)
    if times:
        out["scheduled_time_hint"] = times[0]

    # -----------------------------------------------------------
    # 🎯 Match directo contra proposed_slots usando fecha + hora
    # -----------------------------------------------------------
    if state.get("proposed_slots") and date_iso and times:
        try:
            target_time = _normalize_time_str(times[0])
            tz = ZoneInfo((settings or {}).get("timezone") or "UTC")

            for slot in state["proposed_slots"]:
                start_iso = slot.get("start_iso")
                if not start_iso:
                    continue
                dt = datetime.fromisoformat(start_iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                local_dt = dt.astimezone(tz)

                if local_dt.strftime("%Y-%m-%d") == date_iso and local_dt.strftime("%H:%M") == target_time:
                    out["scheduled_time"] = start_iso
                    break
        except Exception:
            pass

    # ===========================================================
    # 🧠 Unified SAFE scheduled_time construction
    # ===========================================================
    date_hint = out.get("scheduled_date_hint") or state.get("last_date_hint")
    time_hint = out.get("scheduled_time_hint")

    if date_hint and time_hint:

        from dateutil import parser

        # -----------------------------------------------
        # Normalize time ("5"→"05:00", "5pm"→"17:00")
        # -----------------------------------------------
        def normalize_time_str(t: str) -> str:
            t = t.strip().lower()

            # Try smart parser
            try:
                dt = parser.parse(t)
                return dt.strftime("%H:%M")
            except:
                pass

            # If only hour
            if t.isdigit():
                return f"{int(t):02d}:00"

            # Fix formats like "9:0"
            if ":" in t:
                hh, mm = t.split(":", 1)
                hh = f"{int(hh):02d}"
                mm = f"{int(mm):02d}" if mm.isdigit() else "00"
                return f"{hh}:{mm}"

            # Fallback
            return "00:00"

        norm_time = normalize_time_str(time_hint)

        iso_candidate = f"{date_hint}T{norm_time}:00"

        # -----------------------------------------------
        # Validate datetime format
        # -----------------------------------------------
        safe_iso = _safe_datetime(iso_candidate)

        # -----------------------------------------------
        # Apply timezone
        # -----------------------------------------------
        client_tz = None
        if settings and settings.get("timezone"):
            try:
                client_tz = ZoneInfo(settings["timezone"])
            except:
                client_tz = ZoneInfo("UTC")

        if safe_iso:
            dt = datetime.fromisoformat(safe_iso)
            aware = dt.replace(tzinfo=client_tz)
            out["scheduled_time"] = aware.isoformat()

        # Save for next turn
        state["last_date_hint"] = date_hint

    return out


def _normalize_for_match(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", raw).strip()


def _recover_calendar_state_from_history(
    client_id: str,
    session_id: str,
    channel: str,
    settings: dict | None,
    fallback_lang: str,
    *,
    max_age_minutes: int = 180,
) -> dict:
    """
    Recupera estado mínimo del flujo de agenda desde history cuando
    conversation_state no está disponible.
    """
    try:
        res = (
            supabase.table("history")
            .select("role,content,source_type,channel,created_at")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(60)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.warning("⚠️ Could not load history for state recovery: %s", e)
        return {}

    if not rows:
        return {}

    normalized_channel = (channel or "").strip().lower()
    if normalized_channel == "widget":
        normalized_channel = "chat"
    now_utc = datetime.now(timezone.utc)

    recovered = {
        "intent": "calendar",
        "status": "collecting",
        "collected": {},
        "lang": fallback_lang,
    }
    has_appointment_context = False
    user_lang_signal = None
    assistant_lang_signal = None

    for row in rows:
        source_type = str(row.get("source_type") or "").strip().lower()
        if source_type != "appointment":
            continue

        row_channel = str(row.get("channel") or "").strip().lower()
        if row_channel == "widget":
            row_channel = "chat"
        if normalized_channel and row_channel and row_channel != normalized_channel:
            continue

        created_at_raw = str(row.get("created_at") or "").strip()
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_minutes = (now_utc - created_at.astimezone(timezone.utc)).total_seconds() / 60.0
                if age_minutes > max_age_minutes:
                    continue
            except Exception:
                continue

        has_appointment_context = True
        role = str(row.get("role") or "").strip().lower()
        content = str(row.get("content") or "")

        signal_lang = _detect_lang_signal(content)
        if role == "user" and signal_lang:
            user_lang_signal = signal_lang
        if role == "assistant" and signal_lang:
            assistant_lang_signal = signal_lang

        if role == "user":
            extracted = _extract_fields(content, recovered, settings or {})
            for key, value in extracted.items():
                if value:
                    recovered["collected"][key] = value
            continue

        if role == "assistant":
            normalized_content = _normalize_for_match(content)
            if "confirmas la cita" in normalized_content or "do you confirm the appointment" in normalized_content:
                recovered["status"] = "pending_confirmation"
            if (
                "confirmas que ese es tu numero" in normalized_content
                or "do you confirm that's your number" in normalized_content
                or "do you confirm that is your number" in normalized_content
            ):
                recovered["awaiting_whatsapp_phone_confirmation"] = True

    if not has_appointment_context:
        return {}

    if user_lang_signal:
        recovered["lang"] = user_lang_signal
    elif assistant_lang_signal:
        recovered["lang"] = assistant_lang_signal

    collected = recovered.get("collected") or {}
    if (
        collected.get("scheduled_time")
        and collected.get("user_name")
        and collected.get("user_email")
        and collected.get("user_phone")
    ):
        recovered["status"] = "pending_confirmation"
    else:
        recovered["status"] = "collecting"

    return recovered


def _is_explicit_schedule_restart_message(message: str) -> bool:
    text = _normalize_for_match(message)
    if not text:
        return False
    if _is_yes(text) or _is_no(text):
        return False
    if "@" in text:
        return False
    if re.search(r"\+?\d[\d\s\-().]{7,}", message or ""):
        return False
    restart_markers = (
        "quiero agendar",
        "agendar",
        "necesito una cita",
        "quiero una cita",
        "reservar una cita",
        "book appointment",
        "schedule appointment",
    )
    return any(marker in text for marker in restart_markers)



async def handle_calendar_intent(client_id: str, message: str, session_id: str, channel: str, lang: str):
    logger.info(f"🧭 [LLM-Only Mode] Calendar intent for client_id={client_id}")

    # ============================================================
    # 🛡️ Ensure settings always exists
    # ============================================================
    settings = None

    # ============================================================
    # ⚙️ Load calendar settings FIRST
    # ============================================================
    try:
        settings = _load_settings(client_id)
    except Exception as e:
        logger.warning(f"⚠️ Could not load calendar_settings: {e}")
        settings = None

    # ============================================================
    # 🧠 Load previous conversation state
    # ============================================================
    try:
        res = (
            supabase.table("conversation_state")
            .select("state")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        state = _coerce_dict(res.data[0]["state"]) if res and res.data else {}
    except Exception as e:
        logger.warning(f"⚠️ Could not load conversation state: {e}")
        state = {}

    # ✅ Reinicio explícito del flujo cuando el usuario vuelve a pedir agenda.
    # Evita arrastrar datos viejos (email/teléfono/idioma) en sesiones largas.
    if _is_explicit_schedule_restart_message(message):
        state = {
            "intent": "calendar",
            "status": "collecting",
            "collected": {},
            "lang": lang,
        }

    # ✅ Resiliencia: recuperar estado desde history cuando state no existe
    # o viene incompleto para un mensaje que parece nombre.
    current_collected = _coerce_dict(state.get("collected")) if isinstance(state, dict) else {}
    should_try_history_recovery = (
        not state
        or (
            state.get("intent") == "calendar"
            and state.get("status") == "collecting"
            and not current_collected.get("scheduled_time")
            and _looks_like_name(message)
        )
    )
    if should_try_history_recovery:
        recovered_state = _recover_calendar_state_from_history(
            client_id=client_id,
            session_id=session_id,
            channel=channel,
            settings=settings,
            fallback_lang=lang,
        )
        if recovered_state:
            state = recovered_state

    state.setdefault("intent", "calendar")
    state.setdefault("status", "collecting")
    state.setdefault("collected", {})
    state.setdefault("lang", lang)
    signal_lang = _detect_lang_signal(message)
    if signal_lang:
        state["lang"] = signal_lang
    lang = state.get("lang", lang)
    collected = state["collected"]

    # 🛡️ Corregir estado corrupto: nunca permitir pending_confirmation sin horario
    if state.get("status") == "pending_confirmation" and not collected.get("scheduled_time"):
        logger.warning("⚠️ Resetting invalid pending_confirmation state (missing scheduled_time)")
        state["status"] = "collecting"


    # ============================================================
    # 🧩 Extract data from message (NOW settings is safe)
    # ============================================================
    handled_whatsapp_phone_confirmation = False
    new_data = _extract_fields(message, state, settings)

    # ============================================================
    # 📧 EMAIL STRONG VALIDATION — Detect attempts & block invalids
    # ============================================================

    raw_msg = message.strip()

    # 1️⃣ Detecta que el usuario INTENTÓ dar un email, pero no tiene '@'
    looks_like_email_attempt = (
        "@" in raw_msg or
        "." in raw_msg or
        "email" in raw_msg.lower() or
        "correo" in raw_msg.lower()
    )

    # 2️⃣ Si extract_fields detectó un email (bueno o malo)
    if "user_email" in new_data:
        email = new_data["user_email"].strip()

        # But it's invalid → return error
        if not _is_valid_email(email):

            # Remove invalid email from collected
            collected.pop("user_email", None)

            reply = (
                "⚠️ El correo que escribiste no parece válido. ¿Podrías escribirlo de nuevo?"
                if lang == "es"
                else "⚠️ The email you entered doesn’t look valid. Could you write it again?"
            )

            state["collected"] = collected
            supabase.table("conversation_state").upsert(
                {"client_id": client_id, "session_id": session_id, "state": state},
                on_conflict="client_id,session_id",
            ).execute()

            return reply

    # 3️⃣ User typed something email-like but extractor did NOT detect (e.g. “aldo.benitez.cort”)
    elif looks_like_email_attempt and "@" not in raw_msg and "." in raw_msg:

        reply = (
            "⚠️ Parece que intentaste escribir un correo, pero no es válido. Inténtalo de nuevo."
            if lang == "es"
            else "⚠️ It seems like you tried to provide an email, but it’s not valid. Could you write it again?"
        )

        collected.pop("user_email", None)
        state["collected"] = collected
        supabase.table("conversation_state").upsert(
            {"client_id": client_id, "session_id": session_id, "state": state},
            on_conflict="client_id,session_id",
        ).execute()

        return reply

    # 4️⃣ Si el email es válido → guardar normalmente
    for k, v in new_data.items():
        if v:
            collected[k] = v

    # Normalize phone before confirmation/booking to reduce downstream validation failures.
    if collected.get("user_phone"):
        normalized_collected_phone = _normalize_phone_for_booking(
            collected.get("user_phone"),
            session_id,
            channel,
        )
        if normalized_collected_phone:
            collected["user_phone"] = normalized_collected_phone
        state.pop("awaiting_whatsapp_phone_confirmation", None)


    # ============================================================
    # 🔄 Cambiar a pending_confirmation cuando ya tengo todos los datos
    # ============================================================
    if (
        collected.get("user_name")
        and collected.get("user_email")
        and collected.get("user_phone")
        and collected.get("scheduled_time")
        and state.get("status") not in ["pending_confirmation", "confirmed"]
    ):
        logger.info("🟦 Switching status to pending_confirmation (all data collected).")
        state["status"] = "pending_confirmation"
        state.pop("proposed_slots", None)

    # Si ya tenemos todo, confirmar SIEMPRE con respuesta backend (sin LLM) para evitar loops e idioma mixto.
    if (
        state.get("status") == "pending_confirmation"
        and collected.get("user_name")
        and collected.get("user_email")
        and collected.get("user_phone")
        and collected.get("scheduled_time")
        and (handled_whatsapp_phone_confirmation or (not _is_yes(message) and not _is_no(message)))
    ):
        tz_name = (settings or {}).get("timezone") or "UTC"
        pretty_slot = _format_slot_for_lang(collected["scheduled_time"], tz_name, lang)
        confirm_msg = (
            f"Perfecto, {collected['user_name']}. Tengo todo listo.\n"
            f"Tu cita sería el {pretty_slot}.\n"
            "¿Confirmas la cita? (responde: Sí o No)"
            if lang == "es"
            else (
                f"Perfect, {collected['user_name']}. I have everything ready.\n"
                f"Your appointment would be on {pretty_slot}.\n"
                "Do you confirm the appointment? (reply: Yes or No)"
            )
        )

        state["collected"] = collected
        try:
            supabase.table("conversation_state").upsert(
                {"client_id": client_id, "session_id": session_id, "state": state},
                on_conflict="client_id,session_id",
            ).execute()
        except Exception:
            pass
        return confirm_msg



    # ============================================================
    # 🔁 Resolver reemplazo de cita activa (duplicados)
    # ============================================================
    if state.get("status") == "pending_replace_existing":
        if _is_yes(message):
            booking_result = await _book_appointment(
                client_id,
                session_id,
                collected,
                channel,
                replace_existing=True,
            )
            if booking_result.get("ok"):
                state["status"] = "confirmed"
                state.pop("proposed_slots", None)
                state.pop("existing_appointment", None)
                state["collected"] = collected
                try:
                    supabase.table("conversation_state").upsert(
                        {
                            "client_id": client_id,
                            "session_id": session_id,
                            "state": state,
                        },
                        on_conflict="client_id,session_id",
                    ).execute()
                except Exception:
                    pass
                return (
                    "✅ Listo. Cancelé tu cita activa y registré la nueva."
                    if lang == "es"
                    else "✅ Done. I cancelled your active appointment and booked the new one."
                )

            return (
                "❌ No pude reemplazar la cita. Intenta de nuevo en unos minutos."
                if lang == "es"
                else "❌ I couldn't replace the appointment. Please try again in a few minutes."
            )

        if _is_no(message):
            state["status"] = "collecting"
            state.pop("existing_appointment", None)
            collected.pop("scheduled_time", None)
            state["collected"] = collected
            try:
                supabase.table("conversation_state").upsert(
                    {"client_id": client_id, "session_id": session_id, "state": state},
                    on_conflict="client_id,session_id",
                ).execute()
            except Exception:
                pass
            return (
                "Perfecto. Mantengo tu cita actual. Si quieres, te ayudo a elegir otro horario."
                if lang == "es"
                else "Perfect. I'll keep your current appointment. I can help you pick another time."
            )

        existing = state.get("existing_appointment") or {}
        existing_time = existing.get("scheduled_time")
        pretty_existing = existing_time
        try:
            if existing_time:
                tz_name = (settings or {}).get("timezone") or "UTC"
                pretty_existing = _format_slot_for_lang(existing_time, tz_name, lang)
        except Exception:
            pass
        return (
            f"Ya tienes una cita activa ({pretty_existing}). ¿Quieres cancelarla y crear la nueva? (Sí/No)"
            if lang == "es"
            else f"You already have an active appointment ({pretty_existing}). Do you want to cancel it and create the new one? (Yes/No)"
        )

    # ============================================================
    # 📅 Confirmar cita si ya hay horario propuesto
    # ============================================================
    if collected.get("scheduled_time"):
        if (
            state.get("status") == "pending_confirmation"
            and _is_yes(message)
            and not handled_whatsapp_phone_confirmation
        ):

            # Validar slot con settings
            if settings:
                ok, reason = _validate_slot(settings, collected["scheduled_time"])
                if not ok:
                    # Reset invalid slot to avoid infinite confirmation loops.
                    collected.pop("scheduled_time", None)
                    state["status"] = "collecting"
                    state.pop("proposed_slots", None)

                    try:
                        available_slots = _generate_available_slots(settings, client_id)
                        state["proposed_slots"] = available_slots
                    except Exception:
                        state["proposed_slots"] = []

                    state["collected"] = collected
                    try:
                        supabase.table("conversation_state").upsert(
                            {
                                "client_id": client_id,
                                "session_id": session_id,
                                "state": state,
                            },
                            on_conflict="client_id,session_id",
                        ).execute()
                    except Exception:
                        pass

                    tz_name = (settings or {}).get("timezone") or "UTC"
                    slot_text = _format_slot_list_for_lang(
                        state.get("proposed_slots") or [],
                        tz_name,
                        lang,
                    )
                    if not slot_text:
                        return (
                            f"⚠️ Ese horario no cumple reglas: {reason}. No encontré horarios válidos por ahora."
                            if lang == "es"
                            else f"⚠️ That time violates rules: {reason}. I couldn't find valid slots right now."
                        )

                    return (
                        f"⚠️ Ese horario no cumple reglas: {reason}.\n"
                        "Te propongo estos horarios válidos:\n"
                        f"{slot_text}\n"
                        "Elige uno de esta lista."
                        if lang == "es"
                        else (
                            f"⚠️ That time violates rules: {reason}.\n"
                            "Here are valid slots:\n"
                            f"{slot_text}\n"
                            "Choose one from this list."
                        )
                    )


            # ====================================================
            # 💾 Registrar cita en appointments
            # ====================================================
            booking_result = await _book_appointment(client_id, session_id, collected, channel)
            if booking_result.get("ok"):
                state["status"] = "confirmed"
                state.pop("proposed_slots", None)
                state["collected"] = collected

                try:
                    supabase.table("conversation_state").upsert(
                        {
                            "client_id": client_id,
                            "session_id": session_id,
                            "state": state,
                        },
                        on_conflict="client_id,session_id",
                    ).execute()
                except Exception:
                    pass

                # WhatsApp + Email confirmation comes from appointments.create_appointment flow.

                return (
                    "✅ Tu cita ha sido registrada. (Recibirás confirmación pronto.)"
                    if lang == "es"
                    else "✅ Your appointment has been registered. (You’ll receive a confirmation soon.)"
                )
            elif booking_result.get("duplicate_active"):
                state["status"] = "pending_replace_existing"
                state["existing_appointment"] = booking_result.get("existing_appointment") or {}
                state["collected"] = collected
                try:
                    supabase.table("conversation_state").upsert(
                        {
                            "client_id": client_id,
                            "session_id": session_id,
                            "state": state,
                        },
                        on_conflict="client_id,session_id",
                    ).execute()
                except Exception:
                    pass

                existing = booking_result.get("existing_appointment") or {}
                existing_time = existing.get("scheduled_time")
                pretty_existing = existing_time
                try:
                    tz_name = (settings or {}).get("timezone") or "UTC"
                    if existing_time:
                        pretty_existing = _format_slot_for_lang(existing_time, tz_name, lang)
                except Exception:
                    pass
                return (
                    f"Ya tienes una cita activa ({pretty_existing}). ¿Quieres cancelarla y crear la nueva? (Sí/No)"
                    if lang == "es"
                    else f"You already have an active appointment ({pretty_existing}). Do you want to cancel it and create the new one? (Yes/No)"
                )
            else:
                if booking_result.get("invalid_phone"):
                    collected.pop("user_phone", None)
                    state["status"] = "collecting"
                    state["collected"] = collected
                    try:
                        supabase.table("conversation_state").upsert(
                            {
                                "client_id": client_id,
                                "session_id": session_id,
                                "state": state,
                            },
                            on_conflict="client_id,session_id",
                        ).execute()
                    except Exception:
                        pass
                    return (
                        "⚠️ El número debe incluir código de país (ej. +525512345678). ¿Cuál es tu número de WhatsApp?"
                        if lang == "es"
                        else "⚠️ The phone number must include country code (e.g. +15551234567). What is your WhatsApp number?"
                    )
                return (
                    "❌ No pude registrar la cita. Intenta con otro horario."
                    if lang == "es"
                    else "❌ I couldn't register the appointment. Try another time."
                )

    # ============================================================
    # 🔁 Si aún está recopilando datos, actualizar estado
    # ============================================================

    state["collected"] = collected
    try:
        supabase.table("conversation_state").upsert(
            {"client_id": client_id, "session_id": session_id, "state": state},
            on_conflict="client_id,session_id",
        ).execute()
        logger.info(
            f"🧠 Updated conversation state (pre-LLM) for {session_id}: {json.dumps(state, ensure_ascii=False)}"
        )
    except Exception as e:
        logger.error(f"⚠️ Could not persist updated state: {e}")


    # ============================================================
    # 🟦 Generate real available slots (backend-calculated)
    # ============================================================
    try:
        if (settings and state.get("status") == "collecting" and not collected.get("scheduled_time")):
            available_slots = _generate_available_slots(settings, client_id)

            # Guardarlos en el estado para que el LLM NO invente horarios
            state["proposed_slots"] = available_slots

            supabase.table("conversation_state").upsert(
                {
                    "client_id": client_id,
                    "session_id": session_id,
                    "state": state,
                },
                on_conflict="client_id,session_id",
            ).execute()

            logger.info(f"🟦 Proposed slots generated: {len(available_slots)}")
    except Exception as e:
        logger.error(f"❌ Error generating proposed slots: {e}")


    # ============================================================
    # 🧱 Backend-first collecting flow (sin LLM para evitar cambio de idioma)
    # ============================================================
    if state.get("status") == "collecting":
        tz_name = (settings or {}).get("timezone") or "UTC"

        if not collected.get("scheduled_time"):
            proposed_slots = state.get("proposed_slots") or []
            requested_date = str(collected.get("scheduled_date_hint") or state.get("last_date_hint") or "").strip()
            if requested_date:
                day_slots = _filter_slots_for_date(proposed_slots, tz_name, requested_date)
                if day_slots:
                    slot_text = _format_slot_list_for_lang(day_slots, tz_name, lang)
                    return (
                        f"Para {requested_date} tengo estos horarios disponibles:\n{slot_text}\n\nIndícame cuál prefieres."
                        if lang == "es"
                        else f"For {requested_date}, I have these available times:\n{slot_text}\n\nTell me which one you prefer."
                    )

                fallback_text = _format_slot_list_for_lang(proposed_slots, tz_name, lang)
                if fallback_text:
                    return (
                        f"No encontré horarios disponibles para {requested_date}. Estos son los próximos disponibles:\n{fallback_text}\n\nSi quieres otro día, dímelo."
                        if lang == "es"
                        else f"I couldn't find available times for {requested_date}. Here are the next available slots:\n{fallback_text}\n\nIf you want another day, tell me."
                    )

            slot_text = _format_slot_list_for_lang(proposed_slots, tz_name, lang)
            if not slot_text:
                return (
                    "No encontré horarios disponibles por ahora. ¿Quieres intentar otra fecha?"
                    if lang == "es"
                    else "I could not find available slots right now. Do you want to try another date?"
                )
            return (
                "Con gusto te ayudo a agendar tu cita.\n\n"
                "Estos son los próximos horarios disponibles:\n"
                f"{slot_text}\n\n"
                "Indícame cuál prefieres."
                if lang == "es"
                else (
                    "I can help you book your appointment.\n\n"
                    "Here are the next available slots:\n"
                    f"{slot_text}\n\n"
                    "Tell me which one you prefer."
                )
            )

        if not collected.get("user_name"):
            return (
                "Perfecto. ¿Cuál es tu nombre completo?"
                if lang == "es"
                else "Perfect. What is your full name?"
            )

        if not collected.get("user_email"):
            return (
                "Gracias. ¿Cuál es tu correo electrónico?"
                if lang == "es"
                else "Thanks. What is your email address?"
            )

        if not collected.get("user_phone"):
            inferred_whatsapp_phone = _infer_whatsapp_phone_from_session(session_id, channel)
            awaiting_phone_confirmation = bool(state.get("awaiting_whatsapp_phone_confirmation"))
            if inferred_whatsapp_phone:
                if awaiting_phone_confirmation and _is_yes(message):
                    collected["user_phone"] = inferred_whatsapp_phone
                    state["collected"] = collected
                    state.pop("awaiting_whatsapp_phone_confirmation", None)
                    handled_whatsapp_phone_confirmation = True
                elif awaiting_phone_confirmation and _is_no(message):
                    state.pop("awaiting_whatsapp_phone_confirmation", None)
                    state["collected"] = collected
                    try:
                        supabase.table("conversation_state").upsert(
                            {"client_id": client_id, "session_id": session_id, "state": state},
                            on_conflict="client_id,session_id",
                        ).execute()
                    except Exception:
                        pass
                    return (
                        "Perfecto. Compárteme tu número de WhatsApp con código de país (ej. +525512345678)."
                        if lang == "es"
                        else "Perfect. Share your WhatsApp number with country code (e.g. +15551234567)."
                    )
                elif not awaiting_phone_confirmation:
                    state["awaiting_whatsapp_phone_confirmation"] = True
                    state["collected"] = collected
                    try:
                        supabase.table("conversation_state").upsert(
                            {"client_id": client_id, "session_id": session_id, "state": state},
                            on_conflict="client_id,session_id",
                        ).execute()
                    except Exception:
                        pass
                    return (
                        f"Veo que escribes desde {inferred_whatsapp_phone}. ¿Confirmas que ese es tu número para la cita? (Sí/No)"
                        if lang == "es"
                        else f"I see you're messaging from {inferred_whatsapp_phone}. Do you confirm that's your number for the appointment? (Yes/No)"
                    )
                else:
                    return (
                        f"¿Confirmas que {inferred_whatsapp_phone} es tu número de WhatsApp para la cita? (Sí/No)"
                        if lang == "es"
                        else f"Do you confirm {inferred_whatsapp_phone} is your WhatsApp number for the appointment? (Yes/No)"
                    )
            else:
                return (
                    "Gracias. ¿Cuál es tu número de teléfono con WhatsApp?"
                    if lang == "es"
                    else "Thanks. What is your WhatsApp phone number?"
                )

        # We just confirmed WhatsApp phone in this turn. Continue flow without booking yet.
        if handled_whatsapp_phone_confirmation:
            state["status"] = "collecting"
            if (
                collected.get("user_name")
                and collected.get("user_email")
                and collected.get("user_phone")
                and collected.get("scheduled_time")
            ):
                state["status"] = "pending_confirmation"
            state["collected"] = collected
            try:
                supabase.table("conversation_state").upsert(
                    {"client_id": client_id, "session_id": session_id, "state": state},
                    on_conflict="client_id,session_id",
                ).execute()
            except Exception:
                pass
            pretty_slot = _format_slot_for_lang(collected["scheduled_time"], tz_name, lang)
            return (
                f"Perfecto, {collected.get('user_name')}. Tengo todo listo.\n"
                f"Tu cita sería el {pretty_slot}.\n"
                "¿Confirmas la cita? (responde: Sí o No)"
                if lang == "es"
                else (
                    f"Perfect, {collected.get('user_name')}. I have everything ready.\n"
                    f"Your appointment would be on {pretty_slot}.\n"
                    "Do you confirm the appointment? (reply: Yes or No)"
                )
            )



    
    # ============================================================
    # 💬 Generar respuesta LLM si no hay cita confirmada
    # ============================================================
    calendar_prompt = get_calendar_prompt(client_id, collected)
    if not calendar_prompt:
        return "⚠️ No hay configuración activa de calendario para este cliente."


    # ============================================================
    # 🔐 Inject real backend slots into the LLM prompt
    # ============================================================
    slot_text = ""

    if state.get("proposed_slots"):
        try:
            slot_text = "\n".join(
                f"- {s['readable']}"
                for s in state["proposed_slots"]
            )
        except Exception:
            slot_text = "No available slots."

    if slot_text:
        calendar_prompt += (
            "\n\nIMPORTANT:\n"
            "You MUST ONLY offer the following time slots.\n"
            "Do NOT invent new times or modify them.\n"
            "Offer them exactly as listed below:\n\n"
            f"{slot_text}\n\n"
            "If the user writes something like 'Friday at 9', match ONLY if it exists in the list.\n"
            "If not, ask the user to pick one of the listed times.\n"
        )


    # ============================================================
    # 📩 Compose messages for LLM
    # ============================================================
    messages = [
        {"role": "system", "content": calendar_prompt},
        {"role": "user", "content": message},
    ]

    try:
        ai_response = openai_chat(messages, temperature=0.35, use_calendar_model=True)
    except Exception as e:
        logger.error(f"❌ Error invoking LLM calendar prompt: {e}")
        return (
            "❌ Hubo un problema con el asistente de calendario."
            if lang == "es"
            else "❌ There was a problem with the calendar assistant."
        )

        

    # ============================================================
    # 💾 Guardar estado final y respuesta
    # ============================================================
    try:
        supabase.table("conversation_state").upsert(
            {
                "client_id": client_id,
                "session_id": session_id,
                "state": state,
            },
            on_conflict="client_id,session_id",
        ).execute()
        logger.info(f"💾 Final conversation state saved for {session_id}")
    except Exception as e:
        logger.warning(f"⚠️ Could not persist final conversation state: {e}")

    # ============================================================
    # 💬 Respuesta final (usa LLM si es coherente, fallback si no)
    # ============================================================
    if ai_response and len(ai_response.strip()) > 10:
        reply = ai_response.strip()
    else:
        reply = (
            "No pude identificar una fecha u horario. ¿Podrías repetirlo?"
            if lang == "es"
            else "I couldn’t identify a date or time. Could you repeat it?"
        )

    logger.info(f"✅ Final reply to user: {reply[:200]}...")
    return reply
