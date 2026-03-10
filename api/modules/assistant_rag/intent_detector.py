from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

INTENT_CREATE_APPOINTMENT = "create_appointment"
INTENT_CHECK_AVAILABILITY = "check_availability"
INTENT_RESCHEDULE_APPOINTMENT = "reschedule_appointment"
INTENT_CANCEL_APPOINTMENT = "cancel_appointment"
INTENT_CONFIRM_APPOINTMENT = "confirm_appointment"
INTENT_UNKNOWN = "unknown"

SCHEDULING_INTENTS = {
    INTENT_CREATE_APPOINTMENT,
    INTENT_CHECK_AVAILABILITY,
    INTENT_RESCHEDULE_APPOINTMENT,
    INTENT_CANCEL_APPOINTMENT,
    INTENT_CONFIRM_APPOINTMENT,
}

COMMERCIAL_KEYWORDS = {
    "plan",
    "planes",
    "pricing",
    "price",
    "prices",
    "subscription",
    "billing",
    "precio",
    "precios",
    "suscripcion",
    "suscripcion",
    "facturacion",
    "coste",
    "cost",
    "cuanto",
    "cuanto cuesta",
    "premium",
}

SCHEDULE_CORE_TOKENS = {
    "agendar",
    "agenda",
    "cita",
    "consulta",
    "reservar",
    "reservacion",
    "book",
    "schedule",
    "appointment",
    "slot",
    "slots",
    "availability",
    "disponibilidad",
    "horario",
    "horarios",
}

CREATE_PATTERNS = (
    "quiero agendar",
    "agendame",
    "necesito una cita",
    "me gustaria reservar",
    "me gustaria agendar",
    "puedo agendar",
    "quiero reservar",
    "apartar una cita",
    "programar una cita",
    "sacar una cita",
    "agendar con ustedes",
    "me pueden dar una cita",
    "quiero hacer una reservacion",
    "reservar un espacio",
    "book an appointment",
    "schedule an appointment",
    "book appointment",
    "i want to book",
    "i want to schedule",
    "help me book",
    "schedule my appointment",
)

CHECK_AVAILABILITY_PATTERNS = (
    "tienen citas",
    "tienen disponibilidad",
    "que horarios",
    "que dias",
    "que dias",
    "que horarios hay",
    "hay espacio",
    "hay huecos",
    "cuando tienen espacio",
    "cuando puedo agendar",
    "when can i book",
    "available slots",
    "available times",
    "what times",
    "what days",
    "availability",
    "disponibilidad",
    "horarios disponibles",
)

RESCHEDULE_PATTERNS = (
    "reagendar",
    "reprogramar",
    "cambiar mi cita",
    "cambiar la hora",
    "cambiar mi horario",
    "mover mi cita",
    "mover mi horario",
    "necesito otro horario",
    "reschedule",
    "change my appointment",
    "move my appointment",
)

CANCEL_PATTERNS = (
    "cancelar mi cita",
    "cancelar cita",
    "cancelar mi reservacion",
    "cancelar mi reserva",
    "cancel my appointment",
    "i need to cancel",
    "quiero cancelar",
    "necesito cancelar",
    "no podre ir",
    "no podre asistir",
    "no voy a poder ir",
    "anular mi cita",
)

CONFIRM_PATTERNS = (
    "confirmo",
    "confirmar",
    "confirmo la cita",
    "confirmo ese horario",
    "ese horario me funciona",
    "perfecto agendalo",
    "agendalo por favor",
    "agendalo",
    "si quiero ese",
    "me quedo con ese horario",
    "aparta ese",
    "book it",
    "book that one",
    "esta bien",
    "confirm appointment",
    "that slot works",
    "that works for me",
)

SPANISH_WEEKDAYS = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "miércoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "sábado": "saturday",
    "domingo": "sunday",
}
ENGLISH_WEEKDAYS = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
}
WEEKDAY_MAP = {**SPANISH_WEEKDAYS, **ENGLISH_WEEKDAYS}

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
ENGLISH_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
DMY_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
ES_LONG_DATE_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-zñ]+)(?:\s+de\s+(\d{4}))?\b")
EN_LONG_DATE_RE = re.compile(r"\b([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?\b")
DAY_ONLY_RE = re.compile(r"\bel\s+(\d{1,2})\b")
TIME_COLON_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s*(am|pm)?\b")
TIME_PREFIX_RE = re.compile(
    r"\b(?:a las|a la|at)\s+(\d{1,2})(?::([0-5]\d))?\s*(am|pm)?\s*(de la manana|de la mañana|de la tarde|de la noche)?\b"
)
TIME_DAY_PERIOD_RE = re.compile(
    r"\b(\d{1,2})\s*(am|pm)?\s*(de la manana|de la mañana|de la tarde|de la noche)\b"
)


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def _contains_any(haystack: str, needles: set[str]) -> bool:
    return any(n in haystack for n in needles)


def _looks_commercial_only(message_norm: str) -> bool:
    return _contains_any(message_norm, COMMERCIAL_KEYWORDS) and not _contains_any(
        message_norm,
        SCHEDULE_CORE_TOKENS,
    )


def _has_schedule_anchor(message_norm: str) -> bool:
    return _contains_any(message_norm, SCHEDULE_CORE_TOKENS)


def _has_phrase(message_norm: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in message_norm for phrase in phrases)


def _as_iso(dt: date) -> str:
    return dt.isoformat()


def _safe_date(year: int, month: int, day: int) -> str | None:
    try:
        return _as_iso(date(year, month, day))
    except Exception:
        return None


def _resolve_relative_date(message_norm: str) -> str | None:
    if "pasado manana" in message_norm or "day after tomorrow" in message_norm:
        return "day_after_tomorrow"
    if "manana" in message_norm or "tomorrow" in message_norm:
        return "tomorrow"
    if "hoy" in message_norm or "today" in message_norm:
        return "today"
    return None


def _resolve_day_of_week(message_norm: str) -> str | None:
    for token, canonical in WEEKDAY_MAP.items():
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", message_norm):
            return canonical
    return None


def _resolve_day_only(day: int, reference_date: date) -> str | None:
    if day < 1 or day > 31:
        return None
    year = reference_date.year
    month = reference_date.month
    candidate = _safe_date(year, month, day)
    if candidate:
        parsed = date.fromisoformat(candidate)
        if parsed < reference_date:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            candidate = _safe_date(year, month, day)
    return candidate


def _resolve_date(message_norm: str, reference_date: date) -> str | None:
    m = ISO_DATE_RE.search(message_norm)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = DMY_DATE_RE.search(message_norm)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_raw = m.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = reference_date.year
        return _safe_date(year, month, day)

    m = ES_LONG_DATE_RE.search(message_norm)
    if m:
        day = int(m.group(1))
        month = SPANISH_MONTHS.get(m.group(2), 0)
        year = int(m.group(3)) if m.group(3) else reference_date.year
        if month:
            return _safe_date(year, month, day)

    m = EN_LONG_DATE_RE.search(message_norm)
    if m:
        month = ENGLISH_MONTHS.get(m.group(1), 0)
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else reference_date.year
        if month:
            return _safe_date(year, month, day)

    m = DAY_ONLY_RE.search(message_norm)
    if m:
        return _resolve_day_only(int(m.group(1)), reference_date)

    return None


def _resolve_time(message_norm: str) -> str | None:
    def _coerce_time(
        hour_raw: str,
        minute_raw: str | None,
        ampm_raw: str | None,
        day_period_raw: str | None,
    ) -> str | None:
        hour = int(hour_raw)
        minute = int(minute_raw or 0)
        ampm = (ampm_raw or "").strip().lower()
        day_period = (day_period_raw or "").strip().lower()

        if hour > 23 or minute > 59:
            return None

        if ampm:
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
        elif day_period:
            if "tarde" in day_period or "noche" in day_period:
                if 1 <= hour < 12:
                    hour += 12
            if "manana" in day_period and hour == 12:
                hour = 0

        return f"{hour:02d}:{minute:02d}"

    for m in TIME_COLON_RE.finditer(message_norm):
        resolved = _coerce_time(m.group(1), m.group(2), m.group(3), None)
        if resolved:
            return resolved

    for m in TIME_PREFIX_RE.finditer(message_norm):
        resolved = _coerce_time(m.group(1), m.group(2), m.group(3), m.group(4))
        if resolved:
            return resolved

    for m in TIME_DAY_PERIOD_RE.finditer(message_norm):
        resolved = _coerce_time(m.group(1), None, m.group(2), m.group(3))
        if resolved:
            return resolved

    return None


def extract_appointment_entities(message: str, *, reference_date: date | None = None) -> dict[str, str]:
    text = str(message or "")
    message_norm = _normalize(text)
    ref = reference_date or date.today()

    entities: dict[str, str] = {}

    relative_date = _resolve_relative_date(message_norm)
    if relative_date:
        entities["relative_date"] = relative_date

    day_of_week = _resolve_day_of_week(message_norm)
    if day_of_week:
        entities["day_of_week"] = day_of_week

    resolved_date = _resolve_date(message_norm, ref)
    if resolved_date:
        entities["date"] = resolved_date

    resolved_time = _resolve_time(message_norm)
    if resolved_time:
        entities["time"] = resolved_time

    return entities


def _is_cancel_intent(message_norm: str) -> bool:
    if _has_phrase(message_norm, CANCEL_PATTERNS):
        return True
    if re.search(r"\b(cancel|cancelar|anular|anula)\b", message_norm) and (
        "cita" in message_norm or "appointment" in message_norm or "reserv" in message_norm
    ):
        return True
    return False


def _is_reschedule_intent(message_norm: str) -> bool:
    if _has_phrase(message_norm, RESCHEDULE_PATTERNS):
        return True
    if re.search(r"\b(cambiar|mover|move|change|reschedule|reagendar|reprogramar)\b", message_norm) and (
        "cita" in message_norm or "appointment" in message_norm or "horario" in message_norm
    ):
        return True
    return False


def _is_confirm_intent(message_norm: str) -> bool:
    if message_norm.strip() in {"esta bien", "ok", "okay"}:
        return True
    if _has_phrase(message_norm, CONFIRM_PATTERNS):
        return True
    if re.search(r"\b(si|yes)\b.*\b(ese|that one|that slot)\b", message_norm):
        return True
    if re.search(r"\b(confirmo|confirmar|confirm)\b", message_norm):
        return True
    if re.search(r"\b(si|yes)\b", message_norm) and (
        "horario" in message_norm
        or "cita" in message_norm
        or "agenda" in message_norm
        or "slot" in message_norm
    ):
        return True
    return False


def _is_create_intent(message_norm: str, entities: dict[str, str]) -> bool:
    if re.search(r"\b(cuando|when)\b", message_norm) and re.search(
        r"\b(agendar|reservar|book|schedule)\b",
        message_norm,
    ):
        return False
    if _has_phrase(message_norm, CREATE_PATTERNS):
        return True
    if message_norm in {"agendar", "agenda", "reservar", "book", "schedule"}:
        return True
    if re.search(r"\b(agendar|agendame|reservar|programar|apartar|book|schedule|sacar)\b", message_norm):
        return True
    if re.search(r"\b(cita|consulta|appointment)\b", message_norm) and re.search(
        r"\b(quiero|quisiera|necesito|puedo|can i|i want|i need|would like)\b",
        message_norm,
    ):
        return True
    if re.search(r"\b(puedo ir|can i go)\b", message_norm) and (
        entities.get("time") or entities.get("relative_date") or entities.get("day_of_week") or entities.get("date")
    ):
        return True
    if re.search(r"\b(quiero|necesito)\s+a\s+las\b", message_norm):
        return True
    if entities.get("time") and (
        "cita" in message_norm or "agendar" in message_norm or "appointment" in message_norm
    ) and not re.search(r"\b(hay|tienen|tienes)\b", message_norm):
        return True
    return False


def _is_check_availability_intent(message_norm: str, entities: dict[str, str]) -> bool:
    if _has_phrase(message_norm, CHECK_AVAILABILITY_PATTERNS):
        return True
    if re.search(r"\bpuedo\b", message_norm) and entities.get("time") and "?" in message_norm:
        return True
    if re.search(r"\b(tienes|tienen|hay)\s+algo\b", message_norm) and (
        entities.get("time") or entities.get("day_of_week") or entities.get("relative_date") or entities.get("date")
    ):
        return True
    if re.search(r"\b(hay|tienen|when|what|cuandos?|cuales?)\b", message_norm) and (
        "horario" in message_norm
        or "dispon" in message_norm
        or "slot" in message_norm
        or "space" in message_norm
        or "agenda" in message_norm
    ):
        return True
    if re.search(r"\b(puedes|puedo|hay|tienes|tienen)\b", message_norm) and (
        entities.get("day_of_week") or entities.get("relative_date") or entities.get("date")
    ):
        return True
    return False


def detect_appointment_intent(message: str) -> dict[str, Any]:
    """
    Clasifica intención de agenda y extrae entidades de fecha/hora.
    """
    text = str(message or "")
    message_norm = _normalize(text)
    entities = extract_appointment_entities(text)

    if not message_norm:
        return {"intent": INTENT_UNKNOWN, "confidence": 0.0, "entities": entities}

    if _looks_commercial_only(message_norm):
        return {"intent": INTENT_UNKNOWN, "confidence": 0.05, "entities": entities}

    if _is_cancel_intent(message_norm):
        return {"intent": INTENT_CANCEL_APPOINTMENT, "confidence": 0.97, "entities": entities}

    if _is_reschedule_intent(message_norm):
        return {"intent": INTENT_RESCHEDULE_APPOINTMENT, "confidence": 0.95, "entities": entities}

    if _is_confirm_intent(message_norm):
        return {"intent": INTENT_CONFIRM_APPOINTMENT, "confidence": 0.93, "entities": entities}

    if _is_create_intent(message_norm, entities):
        return {"intent": INTENT_CREATE_APPOINTMENT, "confidence": 0.9, "entities": entities}

    if _is_check_availability_intent(message_norm, entities):
        return {"intent": INTENT_CHECK_AVAILABILITY, "confidence": 0.88, "entities": entities}

    if _has_schedule_anchor(message_norm):
        return {"intent": INTENT_CHECK_AVAILABILITY, "confidence": 0.6, "entities": entities}

    return {"intent": INTENT_UNKNOWN, "confidence": 0.0, "entities": entities}


def detect_intent_to_schedule(message: str) -> bool:
    """
    Compatibilidad con el router actual:
    True si el mensaje pertenece al dominio de agenda.
    """
    payload = detect_appointment_intent(message)
    intent = str(payload.get("intent"))
    if intent != INTENT_CONFIRM_APPOINTMENT:
        return intent in SCHEDULING_INTENTS

    normalized = _normalize(message)
    if any(token in normalized for token in ("cita", "horario", "slot", "appointment", "agend", "confirm")):
        return True
    if re.search(r"\b(ese|that)\b", normalized):
        return True
    return False
