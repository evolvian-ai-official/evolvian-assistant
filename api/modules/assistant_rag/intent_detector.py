# ============================================================
# api/modules/assistant_rag/intent_detector.py
# ============================================================
import re
import unicodedata

# --- Util: normalizar acentos y espacios ---
def _normalize(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()

# --- Palabras/expresiones por idioma ---
SPANISH_KEYWORDS = [
    # frases claras
    "quiero agendar", "me gustaria agendar", "puedo agendar", "necesito agendar",
    "quiero una cita", "hacer una cita", "reservar cita", "quiero reservar",
    "programar una cita", "quiero programar", "puedes agendar", "hazme una cita",
    "disponibilidad de cita", "agenda una reunion", "agendar reunion",
    "dame horarios disponibles", "que horarios tienes", "que disponibilidad",
    "horarios disponibles", "disponibilidad para agendar",
    # palabras sueltas (se validan con guardas abajo)
    "agendar", "cita", "sesion", "reagendar", "cambiar mi cita", "modificar mi cita",
    "confirmar cita", "horario", "horarios", "disponible", "disponibilidad",
]

ENGLISH_KEYWORDS = [
    # frases claras
    "book appointment", "make an appointment", "i want to schedule", "i would like to book",
    "i'd like to book", "set up a meeting", "book a meeting", "schedule meeting",
    "schedule a call", "set up a call", "book a time", "arrange a meeting",
    "show available slots", "available times", "when can i book", "find a time",
    "reschedule appointment", "reschedule meeting", "change my appointment",
    "confirm appointment", "book a session", "available schedule",
    # palabras sueltas (validadas con guardas)
    "schedule", "appointment", "meeting", "available", "availability", "book", "slot", "slots",
]

# --- Guardas anti falsos positivos (contextos no transaccionales) ---
NEGATIVE_SPANISH = [
    "agenda de hoy", "mi agenda", "nuestra agenda", "agenda politica",
    "agenda del evento", "agenda semanal", "mi horario laboral", "mi horario de trabajo",
    "horario de atencion", "horario escolar", "horario de clases",
]
NEGATIVE_ENGLISH = [
    "political agenda", "event agenda", "my agenda", "weekly agenda",
    "office hours", "business hours", "class schedule", "school schedule",
]

# --- Patrones útiles ---
# preguntas cortas/muy comunes
SHORT_ES = re.compile(r"^(horarios|horarios\?|disponibilidad\?|disponibilidad|cita\?)$", re.I)
SHORT_EN = re.compile(r"^(availability\?|availability|available times\??|slots\??)$", re.I)

# Expresiones tipo “agendar (el) 15 a las 3 pm”
DATE_TIME_HINT = re.compile(
    r"(agend(ar|ame)|reserv(ar|a)|program(ar|a)|book|schedule).{0,20}"
    r"(\b(hoy|manana|mañana|pasado|lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\b|\b\d{1,2}/\d{1,2}\b|\b\d{1,2}-\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b)",
    re.I,
)

def _contains_any(haystack: str, needles: list[str]) -> bool:
    return any(n in haystack for n in needles)

def _looks_like_schedule_intent(msg_norm: str) -> bool:
    """Estrategia en capas para minimizar falsos positivos."""
    if not msg_norm:
        return False

    # 0) Preguntas cortas
    if SHORT_ES.match(msg_norm) or SHORT_EN.match(msg_norm):
        return True

    # 1) Frases claras (ES + EN)
    if _contains_any(msg_norm, SPANISH_KEYWORDS) or _contains_any(msg_norm, ENGLISH_KEYWORDS):
        # Bloquear contextos informativos/no transaccionales
        if _contains_any(msg_norm, NEGATIVE_SPANISH) or _contains_any(msg_norm, NEGATIVE_ENGLISH):
            # Si hay una pista fuerte de fecha/acción, lo permitimos
            return bool(DATE_TIME_HINT.search(msg_norm))
        return True

    # 2) Patrones suaves con pista de fecha/hora
    if DATE_TIME_HINT.search(msg_norm):
        return True

    # 3) Señales muy débiles: palabras sueltas + signo de pregunta
    if ("horario" in msg_norm or "availability" in msg_norm or "available" in msg_norm) and "?" in msg_norm:
        # si además no cae en negativos, aceptar
        if not (_contains_any(msg_norm, NEGATIVE_SPANISH) or _contains_any(msg_norm, NEGATIVE_ENGLISH)):
            return True

    return False


def detect_intent_to_schedule(message: str) -> bool:
    """
    🧠 Detecta si el usuario tiene intención de agendar/consultar/modificar una cita.
    - Tolerante a acentos/variantes (“agéndame” ≈ “agendame”).
    - Reduce falsos positivos con listas de exclusión.
    - Soporta mensajes muy cortos (“horarios?”, “availability?”).
    """
    if not message:
        return False

    msg_norm = _normalize(message)

    try:
        return _looks_like_schedule_intent(msg_norm)
    except Exception:
        # En caso de cualquier error inesperado, no bloquees la app.
        return False
