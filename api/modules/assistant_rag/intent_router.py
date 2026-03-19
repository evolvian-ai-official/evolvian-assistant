# ============================================================
# Evolvian AI — Intent Router (calendar-sticky + RAG fallback)
# ------------------------------------------------------------
# - Mantiene intent "calendar" pegado por session_id (sticky)
# - Detecta agenda por keywords o bloques de contacto
# - Guarda/lee estado en Supabase (conversation_state)
# - Orquesta con calendar_intent_handler o RAG pipeline
# - Detección de idioma robusta (langdetect o heurística)
# ============================================================

from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import unicodedata
from typing import Any, Dict, Optional
import traceback

# === Dependencias del proyecto ===
from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.assistant_rag.rag_pipeline import ask_question

logger = logging.getLogger(__name__)

# ============================================================
# 🧩 Importar handler de calendario
# ============================================================
try:
    from api.modules.assistant_rag.calendar_intent_handler import handle_calendar_intent as _calendar_handler
    print("✅ calendar_intent_handler importado correctamente.")
except Exception as e:
    print("❌ ERROR importing calendar handler:")
    traceback.print_exc()
    _calendar_handler = None

# ============================================================
# 🧠 Intent detector avanzado (si existe)
# ============================================================
try:
    from api.modules.assistant_rag.intent_detector import (
        detect_appointment_intent as _detect_appointment_intent,
        detect_intent_to_schedule as _detect_intent_to_schedule,
    )
except Exception:
    _detect_appointment_intent = None
    _detect_intent_to_schedule = None

# ============================================================
# ⚙️ Configuración / Constantes
# ============================================================
CS_TABLE = "conversation_state"
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,}")
NAME_LINE_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:[\s\-'][A-Za-zÁÉÍÓÚÑáéíóúñ]+)+$")

AGENDA_KEYWORDS = {
    "agendar", "agenda", "cita", "sesión", "sesion", "reservar",
    "horario", "book", "schedule", "appointment", "slot", "slots",
    "disponible", "disponibles", "availability", "available",
    "dias disponibles", "días disponibles",
}
NON_SCHEDULING_PRODUCT_KEYWORDS = {
    "instagram",
    "instagrma",
    "instgram",
    "insttagrma",
    "facebook",
    "messenger",
    "tiktok",
    "youtube",
    "google business",
    "meta",
    "instalar",
    "isntalar",
    "instalo",
    "instalacion",
    "instalación",
    "installation",
    "integrar",
    "integracion",
    "integración",
    "integration",
    "conectar",
    "conexion",
    "conexión",
    "setup",
    "configurar",
    "configuracion",
    "configuración",
}
CALENDAR_FOLLOWUP_KEYWORDS = {
    "mañana",
    "manana",
    "tomorrow",
    "hoy",
    "today",
    "lunes",
    "martes",
    "miercoles",
    "miércoles",
    "jueves",
    "viernes",
    "sabado",
    "sábado",
    "domingo",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "confirmo",
    "confirmar",
    "confirm",
    "si",
    "sí",
    "yes",
    "primer horario",
    "first slot",
    "de las nueve",
    "de las 9",
    "escoge",
    "elige",
    "choose for me",
    "pick one",
    "mi nombre",
    "my name",
    "mi correo",
    "my email",
    "mi telefono",
    "mi teléfono",
    "my phone",
    "disponible",
    "disponibles",
    "availability",
    "available",
    "que dias",
    "qué días",
    "what days",
}
DATE_LIKE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b", re.I)
TIME_LIKE_RE = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", re.I)
CALENDAR_NAME_STOPWORDS = {
    "instalar",
    "instalo",
    "instagram",
    "como",
    "cómo",
    "puedo",
    "quiero",
    "necesito",
    "ayuda",
    "help",
    "install",
    "setup",
    "configurar",
    "agendar",
    "agenda",
    "cita",
    "horario",
    "disponible",
    "precio",
    "precios",
    "plan",
    "planes",
}
CALENDAR_COMPLETION_MARKERS = (
    "tu cita ha sido registrada",
    "your appointment has been registered",
    "le escribe evolvian",
    "si necesita cancelar",
    "if you need to cancel",
)
CALENDAR_PROGRESS_MARKERS = (
    "cual es tu nombre completo",
    "gracias. cual es tu correo electronico",
    "cual es tu numero de telefono",
    "confirmas la cita",
    "indicame cual prefieres",
    "which one you prefer",
    "what is your full name",
    "what is your email",
    "whatsapp phone number",
)


def _safe_hash(value: Any, *, length: int = 12) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "na"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _safe_tail(value: Any, *, size: int = 8) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "na"
    return raw[-size:]

# ============================================================
# 🌍 Detección de idioma
# ============================================================
def detect_language(text: str) -> str:
    """Detección robusta de idioma (langdetect → heurística)."""
    t = (text or "").lower()

    # Priorizar señales fuertes en español para evitar falsos "en" en frases cortas.
    strong_spanish_signals = {
        "hola",
        "gracias",
        "quiero",
        "necesito",
        "agendar",
        "reservar",
        "cita",
        "sesión",
        "sesion",
        "horario",
        "disponibilidad",
        "correo",
        "estoy",
        "comparando",
        "opciones",
        "incluye",
    }
    if any(c in t for c in "áéíóúñ¿¡") or any(w in t for w in strong_spanish_signals):
        return "es"

    try:
        from langdetect import detect
        code = detect(text or "")
        return "es" if code.startswith("es") else "en"
    except Exception:
        pass

    spanish_words = {
        "hola", "gracias", "quiero", "necesito", "por favor", "cómo", "cita",
        "agendar", "reservar", "dónde", "porque", "favor", "ayuda", "plan",
        "correo", "sesión", "sesion", "horario", "disponible", "agendemos", "agenda"
    }
    if any(c in t for c in "áéíóúñ¿¡") or any(w in t for w in spanish_words):
        return "es"
    return "en"

# ============================================================
# 🧾 Detección de señales de agenda / contacto
# ============================================================
def looks_like_contact_block(message: str) -> bool:
    """True si parece bloque de contacto (nombre + email/teléfono)."""
    if not message:
        return False
    lines = [ln.strip() for ln in message.splitlines() if ln.strip()]
    has_email = any(EMAIL_RE.search(ln) for ln in lines)
    has_phone = any(PHONE_RE.search(ln) for ln in lines)
    has_name = any(NAME_LINE_RE.match(ln) and len(ln.split()) >= 2 for ln in lines)
    return (has_email or has_phone) and has_name

def contains_schedule_keywords(message: str) -> bool:
    """True si contiene palabras de agenda."""
    normalized = _normalize_text(message)
    for keyword in AGENDA_KEYWORDS:
        token = _normalize_text(keyword)
        if not token:
            continue
        if " " in token:
            if token in normalized:
                return True
            continue
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized):
            return True
    return False


def _looks_like_person_name_for_calendar(message: str) -> bool:
    raw = str(message or "").strip()
    if not raw:
        return False
    if EMAIL_RE.search(raw) or PHONE_RE.search(raw):
        return False
    if any(ch.isdigit() for ch in raw):
        return False

    normalized = _normalize_text(raw)
    tokens = [tok for tok in re.split(r"\s+", normalized) if tok]
    if len(tokens) < 2 or len(tokens) > 5:
        return False
    if any(tok in CALENDAR_NAME_STOPWORDS for tok in tokens):
        return False
    return bool(NAME_LINE_RE.match(raw))


def _looks_like_calendar_followup(message: str) -> bool:
    """Detecta respuestas típicas de 2º/3º turno en flujo de agenda."""
    if not message:
        return False
    if EMAIL_RE.search(message) or PHONE_RE.search(message):
        return True
    # Permite recuperar flujo cuando el usuario responde solo su nombre completo.
    # Ejemplo real: "Aldo Nicolas Benitez".
    if _looks_like_person_name_for_calendar(message):
        return True

    normalized = _normalize_text(message)
    if any(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized) for token in CALENDAR_FOLLOWUP_KEYWORDS):
        return True

    # Inputs como "mañana 9:00", "2026-03-10 09:00", "10/03/2026 9am".
    if DATE_LIKE_RE.search(message) or TIME_LIKE_RE.search(message):
        return True
    return False


def _looks_like_non_scheduling_product_query(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    has_product_marker = any(marker in normalized for marker in NON_SCHEDULING_PRODUCT_KEYWORDS)
    if not has_product_marker:
        return False
    # Keep booking path available for explicit scheduling requests.
    if contains_schedule_keywords(message) or _looks_like_calendar_followup(message) or looks_like_contact_block(message):
        return False
    return True


def _parse_created_at(raw_value: Any) -> Optional[datetime]:
    try:
        raw = str(raw_value or "").strip()
        if not raw:
            return None
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _has_recent_appointment_history(
    client_id: str,
    session_id: str,
    channel: str,
    *,
    max_age_minutes: int = 120,
) -> bool:
    """
    Fallback de resiliencia:
    si state falla en persistir/leer, usa history reciente para decidir
    si el usuario sigue en flujo de agenda.
    """
    try:
        res = (
            supabase.table("history")
            .select("source_type, channel, content, created_at")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(8)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.warning("Could not load recent history context for fallback routing: %s", e)
        return False

    if not rows:
        return False

    now_utc = datetime.now(timezone.utc)
    normalized_channel = _normalize_channel_name(channel)
    saw_recent_progress = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        created_at = _parse_created_at(row.get("created_at"))
        if not created_at:
            continue
        age_minutes = (now_utc - created_at).total_seconds() / 60.0
        if age_minutes > max_age_minutes:
            continue

        row_channel = _normalize_channel_name(row.get("channel"))
        if row_channel and row_channel != normalized_channel:
            continue

        content = _normalize_text(str(row.get("content") or ""))
        if any(marker in content for marker in CALENDAR_COMPLETION_MARKERS):
            return False

        if str(row.get("source_type") or "").strip().lower() == "appointment":
            saw_recent_progress = True

        if (
            "horarios disponibles" in content
            or "available slots" in content
            or any(marker in content for marker in CALENDAR_PROGRESS_MARKERS)
        ):
            saw_recent_progress = True
    return saw_recent_progress


def detect_intent_to_schedule(message: str) -> bool:
    """Wrapper: detector avanzado o fallback local."""
    if _looks_like_non_scheduling_product_query(message):
        return False
    if _detect_appointment_intent:
        try:
            detected = _detect_appointment_intent(message) or {}
            intent = str(detected.get("intent") or "").strip().lower()
            if intent == "confirm_appointment":
                normalized = _normalize_text(message)
                if any(
                    token in normalized
                    for token in ("cita", "horario", "slot", "appointment", "agend", "confirm", "ese", "that")
                ):
                    return True
            # Avoid routing generic confirmations ("ok", "está bien") to calendar.
            if intent == "confirm_appointment":
                return False
            if intent in {
                "create_appointment",
                "check_availability",
                "reschedule_appointment",
                "cancel_appointment",
            }:
                return True
        except Exception:
            pass
    if _detect_intent_to_schedule:
        try:
            # If advanced detector is uncertain/false, keep robust local fallback
            # so obvious scheduling phrasing still routes to calendar.
            if bool(_detect_intent_to_schedule(message)):
                return True
        except Exception:
            pass
    return contains_schedule_keywords(message) or looks_like_contact_block(message)

# ============================================================
# 💾 Estado conversacional (Supabase)
# ============================================================
def _coerce_dict(val: Any) -> Dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}

def get_state(client_id: str, session_id: str) -> Dict:
    try:
        res = (
            supabase.table(CS_TABLE)
            .select("state")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        if not res or not getattr(res, "data", None):
            return {}
        return _coerce_dict(res.data[0].get("state"))
    except Exception as e:
        print(f"⚠️ get_state error: {e}")
        return {}


def _is_on_conflict_constraint_error(exc: Exception) -> bool:
    raw = str(exc or "").lower()
    return (
        "42p10" in raw
        or "no unique or exclusion constraint matching the on conflict specification" in raw
    )


def upsert_state(client_id: str, session_id: str, state: Dict) -> None:
    payload = {
        "client_id": client_id,
        "session_id": session_id,
        "state": state or {},
    }
    try:
        supabase.table(CS_TABLE).upsert(
            payload,
            on_conflict="client_id,session_id",
        ).execute()
    except Exception as e:
        if _is_on_conflict_constraint_error(e):
            try:
                existing = (
                    supabase.table(CS_TABLE)
                    .select("client_id")
                    .eq("client_id", client_id)
                    .eq("session_id", session_id)
                    .limit(1)
                    .execute()
                )
                has_existing = bool(existing and getattr(existing, "data", None))
                if has_existing:
                    (
                        supabase.table(CS_TABLE)
                        .update({"state": state or {}})
                        .eq("client_id", client_id)
                        .eq("session_id", session_id)
                        .execute()
                    )
                else:
                    supabase.table(CS_TABLE).insert(payload).execute()
                print("⚠️ upsert_state fallback applied (missing on_conflict constraint)")
                return
            except Exception as fallback_exc:
                print(f"⚠️ upsert_state fallback error: {fallback_exc}")
                return
        print(f"⚠️ upsert_state error: {e}")

def get_active_intent(client_id: str, session_id: str) -> Optional[str]:
    state = get_state(client_id, session_id)
    return state.get("intent") if isinstance(state.get("intent"), str) else None

def set_intent(client_id: str, session_id: str, intent: str) -> None:
    state = get_state(client_id, session_id)
    state["intent"] = intent
    state.setdefault("collected", {})
    state.setdefault("status", "collecting")
    upsert_state(client_id, session_id, state)


def _normalize_channel_name(raw: str | None) -> str:
    c = (raw or "chat").strip().lower()
    if c in {"widget", "web", "chat_widget"}:
        return "chat"
    if "whatsapp" in c:
        return "whatsapp"
    return c


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _detect_institutional_auto_reply(message: str, channel: str) -> dict[str, Any] | None:
    normalized_channel = _normalize_channel_name(channel)
    if normalized_channel not in {"whatsapp", "email", "messenger", "instagram"}:
        return None

    text = _normalize_text(message).strip()
    if not text:
        return None

    strong_markers = (
        "mensaje automatico",
        "respuesta automatica",
        "este es un mensaje automatico",
        "auto reply",
        "autoreply",
        "out of office",
        "away message",
        "do not reply",
        "noreply",
        "no-reply",
    )
    institutional_markers = (
        "gracias por comunicarte",
        "gracias por comunicarse",
        "gracias por contactarnos",
        "gracias por comunicarte con",
        "gracias por comunicarse con",
        "thank you for contacting",
        "thanks for contacting",
        "thanks for reaching out",
        "hemos recibido tu mensaje",
        "recibimos tu mensaje",
        "we received your message",
        "como podemos ayudarte",
        "how can we help you",
        "can i help you",
        "en breve te atendemos",
        "en breve lo atendemos",
        "en breve nos comunicaremos con usted",
        "en breve nos comunicaremos contigo",
        "en breve nos pondremos en contacto",
        "te responderemos en breve",
        "nos comunicaremos con usted",
        "nos comunicaremos contigo",
        "nuestro equipo te respondera",
        "our team will reply",
        "fuera de horario",
        "horario de atencion",
        "business hours",
    )
    strong_hits = [marker for marker in strong_markers if marker in text]
    institutional_hits = [marker for marker in institutional_markers if marker in text]

    if not strong_hits and len(institutional_hits) < 2:
        return None

    return {
        "event": "institutional_auto_reply_detected",
        "channel": normalized_channel,
        "signals": (strong_hits + institutional_hits)[:4],
    }


def _is_whatsapp_handoff_request(message: str) -> bool:
    text = _normalize_text(message).strip()
    if not text:
        return False
    phrases = (
        "quiero humano",
        "agente humano",
        "asesor humano",
        "hablar con humano",
        "hablar con agente",
        "pasame con humano",
        "pasame con un agente",
        "persona real",
        "quiero hablar con alguien",
        "human agent",
        "real person",
        "talk to an agent",
        "speak to an agent",
        "connect me with support",
    )
    return any(p in text for p in phrases)


def _scope_redirect_message(lang: str) -> str:
    if lang == "en":
        return (
            "I can help with questions related to this business. "
            "If you tell me what you need about services, pricing, appointments, or support, "
            "I can help right now."
        )
    return (
        "Puedo ayudarte con consultas relacionadas con este negocio. "
        "Si me dices qué necesitas sobre servicios, precios, citas o soporte, te ayudo ahora mismo."
    )


def _scope_outside_message(lang: str) -> str:
    if lang == "en":
        return (
            "That question is outside what I can resolve here. "
            "If you want, I can connect you with a human agent to review it."
        )
    return "Esa consulta está fuera de lo que puedo resolver aquí. Si quieres, te conecto con un agente humano para revisarlo."


def _whatsapp_handoff_confirmation_message(lang: str) -> str:
    if lang == "en":
        return (
            "Thanks. A human agent is now reviewing this and we will reply as soon as possible "
            "through this same chat."
        )
    return (
        "Gracias. Ya lo estamos revisando con un agente humano y te responderemos "
        "lo más pronto posible por este mismo chat."
    )


def _campaign_interest_followup_message(lang: str) -> str:
    if lang == "en":
        return (
            "Thanks for your interest. A human advisor is already following up with you "
            "directly in this chat."
        )
    return (
        "Gracias por tu interés. Un asesor humano ya está dando seguimiento contigo "
        "directamente por este chat."
    )


def _is_campaign_interest_followup(message: str) -> bool:
    text = _normalize_text(message).strip()
    if not text:
        return False
    markers = (
        "me interesa",
        "interesado",
        "interesada",
        "que sigue",
        "qué sigue",
        "siguiente paso",
        "quiero info",
        "mas info",
        "más info",
        "asesor",
        "advisor",
        "follow up",
        "followup",
    )
    return any(re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) for marker in markers)


def _get_active_campaign_interest_handoff(client_id: str, session_id: str) -> dict[str, Any] | None:
    try:
        res = (
            supabase.table("conversation_handoff_requests")
            .select("id,status,assigned_user_id,reason,trigger,updated_at")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .eq("channel", "whatsapp")
            .in_("reason", ["campaign_interest"])
            .in_("status", ["open", "assigned", "in_progress"])
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        return row if isinstance(row, dict) else None
    except Exception as e:
        logger.warning("Could not read active campaign-interest handoff for session=%s: %s", session_id, e)
        return None


def _extract_phone_from_session(session_id: str) -> str | None:
    raw = str(session_id or "").strip()
    if not raw:
        return None
    if raw.startswith("whatsapp-"):
        raw = raw[len("whatsapp-") :]
    cleaned = re.sub(r"[^\d+]", "", raw)
    return cleaned or None


def _last_assistant_was_scope_redirect(client_id: str, session_id: str) -> bool:
    try:
        res = (
            supabase.table("history")
            .select("metadata")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .eq("channel", "whatsapp")
            .eq("role", "assistant")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        if not row:
            return False
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            metadata = _coerce_dict(metadata)
        if not isinstance(metadata, dict):
            return False
        policy = metadata.get("whatsapp_policy")
        if not isinstance(policy, dict):
            return False
        return str(policy.get("event") or "") == "out_of_scope_redirect"
    except Exception as e:
        logger.warning("Could not resolve previous WhatsApp scope marker: %s", e)
        return False


def _client_has_handoff_feature(client_id: str) -> bool:
    try:
        from api.utils.feature_access import client_has_active_feature

        return bool(client_has_active_feature(client_id, "handoff"))
    except Exception as e:
        logger.warning("Could not validate handoff feature for client %s: %s", client_id, e)
        return False


def _upsert_whatsapp_handoff(
    *,
    client_id: str,
    session_id: str,
    user_message: str,
    ai_message: str,
    trigger: str,
    reason: str,
    language: str,
    metadata_origin: str = "whatsapp_policy",
    metadata_extra: Optional[dict[str, Any]] = None,
    alert_type: str = "human_intervention",
    alert_priority: str = "normal",
    alert_title: str = "Human intervention requested",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "feature_enabled": False,
        "handoff_id": None,
        "conversation_id": None,
        "alert_created": False,
        "reused": False,
    }
    if not _client_has_handoff_feature(client_id):
        logger.info(
            "WhatsApp handoff skipped (feature disabled) | client_ref=%s | session_fp=%s | trigger=%s | reason=%s",
            _safe_tail(client_id),
            _safe_hash(session_id),
            str(trigger or ""),
            str(reason or ""),
        )
        return result

    result["feature_enabled"] = True
    now_iso = datetime.now(timezone.utc).isoformat()
    phone = _extract_phone_from_session(session_id)
    contact_name = "WhatsApp user"
    if phone and len(phone) >= 4:
        contact_name = f"WhatsApp user {phone[-4:]}"

    conversation_id = None
    try:
        convo_res = (
            supabase.table("conversations")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .maybe_single()
            .execute()
        )
        if convo_res and convo_res.data:
            conversation_id = convo_res.data.get("id")
            (
                supabase.table("conversations")
                .update(
                    {
                        "status": "needs_human",
                        "primary_channel": "whatsapp",
                        "contact_name": contact_name,
                        "contact_phone": phone,
                        "latest_message_at": now_iso,
                        "last_message_preview": (user_message or ai_message or "")[:240] or None,
                        "updated_at": now_iso,
                    }
                )
                .eq("id", conversation_id)
                .eq("client_id", client_id)
                .execute()
            )
        else:
            convo_insert = (
                supabase.table("conversations")
                .insert(
                    {
                        "client_id": client_id,
                        "session_id": session_id,
                        "status": "needs_human",
                        "primary_channel": "whatsapp",
                        "contact_name": contact_name,
                        "contact_phone": phone,
                        "latest_message_at": now_iso,
                        "last_message_preview": (user_message or ai_message or "")[:240] or None,
                        "updated_at": now_iso,
                    }
                )
                .execute()
            )
            if convo_insert and convo_insert.data:
                conversation_id = convo_insert.data[0].get("id")
    except Exception as e:
        logger.warning("Could not upsert conversation for WhatsApp handoff: %s", e)

    result["conversation_id"] = conversation_id
    logger.info(
        "WhatsApp handoff conversation upserted | client_ref=%s | session_fp=%s | conversation_ref=%s",
        _safe_tail(client_id),
        _safe_hash(session_id),
        _safe_tail(conversation_id),
    )

    handoff_id = None
    try:
        open_res = (
            supabase.table("conversation_handoff_requests")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .eq("channel", "whatsapp")
            .in_("status", ["open", "assigned", "in_progress"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        open_row = (open_res.data or [None])[0]
        if open_row:
            handoff_id = open_row.get("id")
            result["reused"] = True
            (
                supabase.table("conversation_handoff_requests")
                .update(
                    {
                        "conversation_id": conversation_id,
                        "contact_name": contact_name,
                        "contact_phone": phone,
                        "trigger": trigger,
                        "reason": reason,
                        "status": "open",
                        "resolved_at": None,
                        "last_user_message": (user_message or "").strip() or None,
                        "last_ai_message": (ai_message or "").strip() or None,
                        "updated_at": now_iso,
                    }
                )
                .eq("id", handoff_id)
                .eq("client_id", client_id)
                .execute()
            )
            logger.info(
                "WhatsApp handoff reused | client_ref=%s | session_fp=%s | handoff_ref=%s",
                _safe_tail(client_id),
                _safe_hash(session_id),
                _safe_tail(handoff_id),
            )
        else:
            metadata = {
                "language": "en" if language == "en" else "es",
                "auto_handoff": True,
                "origin": metadata_origin,
            }
            if isinstance(metadata_extra, dict):
                metadata.update(metadata_extra)
            insert_res = (
                supabase.table("conversation_handoff_requests")
                .insert(
                    {
                        "client_id": client_id,
                        "conversation_id": conversation_id,
                        "session_id": session_id,
                        "channel": "whatsapp",
                        "trigger": trigger,
                        "reason": reason,
                        "status": "open",
                        "contact_name": contact_name,
                        "contact_phone": phone,
                        "accepted_terms": True,
                        "accepted_email_marketing": False,
                        "last_user_message": (user_message or "").strip() or None,
                        "last_ai_message": (ai_message or "").strip() or None,
                        "metadata": metadata,
                        "updated_at": now_iso,
                    }
                )
                .execute()
            )
            if insert_res and insert_res.data:
                handoff_id = insert_res.data[0].get("id")
                logger.info(
                    "WhatsApp handoff created | client_ref=%s | session_fp=%s | handoff_ref=%s",
                    _safe_tail(client_id),
                    _safe_hash(session_id),
                    _safe_tail(handoff_id),
                )
    except Exception as e:
        logger.warning("Could not create/update WhatsApp handoff request: %s", e)

    result["handoff_id"] = handoff_id
    if not handoff_id:
        return result

    try:
        existing_alert_res = (
            supabase.table("conversation_alerts")
            .select("id,status")
            .eq("client_id", client_id)
            .eq("source_handoff_request_id", handoff_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        existing_alert = (existing_alert_res.data or [None])[0] if existing_alert_res else None
        if existing_alert:
            (
                supabase.table("conversation_alerts")
                .update(
                    {
                        "conversation_id": conversation_id,
                        "status": "open",
                        "resolved_at": None,
                        "priority": str(alert_priority or "normal"),
                        "title": str(alert_title or "Human intervention requested"),
                        "body": (user_message or ai_message or "WhatsApp escalation request")[:500],
                    }
                )
                .eq("id", existing_alert.get("id"))
                .eq("client_id", client_id)
                .execute()
            )
            result["alert_created"] = True
            logger.info(
                "WhatsApp handoff alert reopened | client_ref=%s | handoff_ref=%s | alert_ref=%s",
                _safe_tail(client_id),
                _safe_tail(handoff_id),
                _safe_tail(existing_alert.get("id")),
            )
            return result

        alert_res = (
            supabase.table("conversation_alerts")
            .insert(
                {
                    "client_id": client_id,
                    "conversation_id": conversation_id,
                    "source_handoff_request_id": handoff_id,
                    "alert_type": str(alert_type or "human_intervention"),
                    "status": "open",
                    "priority": str(alert_priority or "normal"),
                    "title": str(alert_title or "Human intervention requested"),
                    "body": (user_message or ai_message or "WhatsApp escalation request")[:500],
                }
            )
            .execute()
        )
        result["alert_created"] = bool(alert_res and getattr(alert_res, "data", None))
        created_alert_id = None
        if alert_res and getattr(alert_res, "data", None):
            first_row = (alert_res.data or [None])[0]
            if isinstance(first_row, dict):
                created_alert_id = first_row.get("id")
        logger.info(
            "WhatsApp handoff alert created | client_ref=%s | handoff_ref=%s | alert_ref=%s | created=%s",
            _safe_tail(client_id),
            _safe_tail(handoff_id),
            _safe_tail(created_alert_id),
            bool(result["alert_created"]),
        )
    except Exception as e:
        logger.warning("Could not upsert WhatsApp alert for handoff=%s: %s", handoff_id, e)

    return result

# ============================================================
# 🚦 Router lógico
# ============================================================
def route_message(client_id: str, session_id: str, message: str, channel: str = "chat") -> str:
    """
    Devuelve: "calendar" | "rag"
    Mantiene el intent 'calendar' activo mientras el flujo esté en progreso.
    Permite salir del flujo solo si el usuario realmente cambia de tema.
    """
    # 🎨 Colores para logs
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"

    text = (message or "").lower().strip()

    PRICING_HINTS = {
        "plan", "planes", "pricing", "price", "prices", "subscription", "billing",
        "precio", "precios", "suscripción", "suscripcion", "coste", "cost", "cuanto", "cuánto",
    }
    PRODUCT_HELP_HINTS = {
        "instagram",
        "instagrma",
        "instgram",
        "insttagrma",
        "facebook",
        "messenger",
        "tiktok",
        "integracion",
        "integración",
        "integrate",
        "integration",
        "instalar",
        "isntalar",
        "instalo",
        "installation",
        "setup",
        "configurar",
        "configuracion",
        "configuración",
    }
    SCHEDULING_HINTS = {
        "agendar", "reservar", "reagendar", "cita", "citas", "sesion", "sesión",
        "book", "schedule", "appointment", "reschedule", "slot", "slots",
        "horario", "horarios", "disponibilidad", "availability",
    }

    # Priorizar preguntas comerciales simples (planes/precios) para evitar falsos positivos.
    if any(k in text for k in PRICING_HINTS) and not any(k in text for k in SCHEDULING_HINTS):
        upsert_state(client_id, session_id, {"intent": None})
        return "rag"
    if any(k in text for k in PRODUCT_HELP_HINTS) and not any(k in text for k in SCHEDULING_HINTS):
        upsert_state(client_id, session_id, {"intent": None})
        return "rag"

    GREETINGS = {"hola", "buenas", "hey", "hi", "hello"}
    GENERIC_INFO = {
        "información", "informacion", "planes", "precios", "ayuda", "gracias",
        "servicios", "productos", "qué es", "que es"
    }

    # 🧠 Detectar agenda ANTES de ignorar saludos
    if detect_intent_to_schedule(message):
        print(f"{GREEN}📅 Schedule intent detected (ignoring greeting){RESET}")
    else:
        # 🧹 Saludos y preguntas generales → modo RAG
        if any(text.startswith(g) for g in GREETINGS) or any(k in text for k in GENERIC_INFO):
            print(f"{YELLOW}🔄 Resetting intent for general message: '{message}'{RESET}")
            upsert_state(client_id, session_id, {"intent": None})
            return "rag"

    # 📍 Estado actual
    active_state = get_state(client_id, session_id)
    active_intent = active_state.get("intent")
    status = active_state.get("status", "")

    # 🆕 Palabras que indican que el usuario quiere SALIR del flujo de agenda
    EXIT_CALENDAR_KEYWORDS = {
        "price", "prices", "plan", "plans", "premium", "starter", "free",
        "cost", "how much", "billing", "upgrade", "downgrade",
        "precio", "precios", "cuanto", "coste", "planes",
        "instagram", "facebook", "messenger", "tiktok",
        "instalar", "instalo", "instalacion", "installation",
        "integracion", "integration", "setup", "configurar", "configuracion",
    }

    def user_wants_to_exit_calendar(msg: str) -> bool:
        t = _normalize_text(msg)
        return any(k in t for k in EXIT_CALENDAR_KEYWORDS)

    def _is_truthy(val: Any, default: bool = True) -> bool:
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in {"1", "true", "yes", "on"}
        return bool(val)

    def _normalize_channel(raw: str | None) -> str:
        c = (raw or "chat").strip().lower()
        if c in {"widget", "web", "chat_widget"}:
            return "chat"
        if "whatsapp" in c:
            return "whatsapp"
        return c

    def get_calendar_gate() -> tuple[bool, str | None]:
        try:
            from api.utils.plan_features_logic import client_has_feature
            has_calendar_feature = client_has_feature(client_id, "calendar_sync")
            res = (
                supabase.table("calendar_settings")
                .select("*")
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            )
            settings = res.data or {}
            calendar_status = settings.get("calendar_status") if settings else None
            if not (has_calendar_feature and calendar_status == "active"):
                return False, calendar_status

            normalized_channel = _normalize_channel(channel)
            chat_ai_enabled = _is_truthy(settings.get("ai_scheduling_chat_enabled"), True)
            wa_ai_enabled = _is_truthy(settings.get("ai_scheduling_whatsapp_enabled"), True)

            if normalized_channel == "whatsapp" and not wa_ai_enabled:
                return False, calendar_status
            if normalized_channel in {"chat", "widget"} and not chat_ai_enabled:
                return False, calendar_status

            return True, calendar_status
        except Exception:
            return False, None

    # 📅 Mantener sticky intent (pero permitir salir si cambia de tema)
    if active_intent == "calendar" and status in [
        "collecting",
        "pending_confirmation",
        "pending_replace_existing",
    ]:
        calendar_enabled, calendar_status = get_calendar_gate()
        if not calendar_enabled:
            print(f"{YELLOW}🧹 Calendar sticky cleared (status={calendar_status}){RESET}")
            upsert_state(client_id, session_id, {"intent": None})
            lang = detect_language(message)
            return (
                "⚠️ La agenda está desactivada en este momento."
                if lang == "es"
                else "⚠️ Scheduling is currently disabled."
            )

        # 🚪 El usuario explícitamente cambia de tema → SALIR DEL FLUJO
        if user_wants_to_exit_calendar(message):
            print(f"{YELLOW}🚪 Topic changed → exiting calendar flow{RESET}")
            upsert_state(client_id, session_id, {"intent": None})
            return "rag"

        # 👉 Si sigue en agenda aunque diga nombre/email/etc → CONTINUAR
        print(f"{GREEN}🧠 Continuing calendar flow (status={status}){RESET}")
        return "calendar"

    # 🔧 Resiliencia: recuperar flujo de agenda por historial reciente
    # cuando conversation_state no esté disponible en producción.
    if active_intent != "calendar" and _looks_like_calendar_followup(message):
        recent_appointment_context = _has_recent_appointment_history(
            client_id,
            session_id,
            channel,
        )
        if recent_appointment_context:
            calendar_enabled, calendar_status = get_calendar_gate()
            if calendar_enabled:
                recovered_state = get_state(client_id, session_id)
                recovered_state.setdefault("collected", {})
                recovered_state.update(
                    {
                        "intent": "calendar",
                        "status": "collecting",
                        "calendar_status": calendar_status,
                        "has_calendar_feature": True,
                    }
                )
                upsert_state(client_id, session_id, recovered_state)
                print(f"{GREEN}🛟 Recovered calendar flow from recent history{RESET}")
                return "calendar"

    # 🕵️ Activar flujo calendario desde cero
    if detect_intent_to_schedule(message):
        try:
            calendar_enabled, calendar_status = get_calendar_gate()
            print(f"📡 Client={client_id} | status={calendar_status} | enabled={calendar_enabled}")

            # 🚫 Bloqueo si no aplica
            if not calendar_enabled:
                lang = detect_language(message)
                print(f"{RED}🚫 Calendar intent blocked{RESET}")
                return (
                    "⚠️ Tu agenda está desactivada en este momento."
                    if lang == "es"
                    else "⚠️ Scheduling is currently disabled."
                )

            # ✅ Activar calendario
            set_intent(client_id, session_id, "calendar")

            state = get_state(client_id, session_id)
            state.update({
                "intent": "calendar",
                "status": "collecting",
                "calendar_status": calendar_status,
                "has_calendar_feature": True,
            })
            upsert_state(client_id, session_id, state)

            print(f"{GREEN}✅ Calendar intent ACTIVATED{RESET}")
            return "calendar"

        except Exception as e:
            print(f"{RED}⚠️ Error verifying calendar feature: {e}{RESET}")

    # 🧹 Si había calendar pero ya no aplica (esto es fallback)
    if active_intent == "calendar":
        print(f"{YELLOW}🧹 Calendar intent cleared (fallback){RESET}")
        upsert_state(client_id, session_id, {"intent": None})
        return "rag"

    # 💬 Default → RAG
    print(f"{YELLOW}💬 Routing → RAG (default){RESET}")
    return "rag"



# ============================================================
# 🎯 Orquestador principal (router + handlers)
# ============================================================
async def process_user_message(
    client_id: str,
    session_id: str,
    message: str,
    channel: str = "chat",
    provider: str = "internal",
    return_metadata: bool = False,
):
    """
    Entrada principal de intents:
    - Detecta idioma
    - Enruta al calendario si aplica
    - Si no, usa el pipeline RAG
    """
    print(f"🤖 [Router] Processing message from {channel}: {message}")
    lang = detect_language(message)
    print(f"🌍 Detected language: {lang}")
    normalized_channel = _normalize_channel_name(channel)
    is_whatsapp = normalized_channel == "whatsapp"
    auto_reply_policy = _detect_institutional_auto_reply(message, normalized_channel)
    if auto_reply_policy:
        save_history(
            client_id,
            session_id,
            "user",
            message,
            channel=channel,
            provider=provider,
            metadata={"message_policy": auto_reply_policy},
        )
        logger.info(
            "Suppressed institutional auto-reply | channel=%s | client_ref=%s | session_fp=%s | signals=%s",
            normalized_channel,
            _safe_tail(client_id),
            _safe_hash(session_id),
            auto_reply_policy.get("signals"),
        )
        if return_metadata:
            return {
                "answer": "",
                "confidence_score": 1.0,
                "handoff_recommended": False,
                "human_intervention_recommended": False,
                "needs_human": False,
                "handoff_reason": None,
                "confidence_reason": "institutional_auto_reply_suppressed",
                "no_reply": True,
            }
        return None

    if is_whatsapp:
        campaign_interest_handoff = _get_active_campaign_interest_handoff(client_id, session_id)
        if campaign_interest_handoff:
            # Use deterministic local signals here to avoid false positives from
            # advanced intent detectors and keep campaign follow-up stable.
            is_schedule_message = contains_schedule_keywords(message) or _looks_like_calendar_followup(message)
            if not is_schedule_message and _is_campaign_interest_followup(message):
                answer = _campaign_interest_followup_message(lang)
                save_history(
                    client_id,
                    session_id,
                    "user",
                    message,
                    channel=channel,
                    provider=provider,
                )
                save_history(
                    client_id,
                    session_id,
                    "assistant",
                    answer,
                    channel=channel,
                    provider=provider,
                    metadata={
                        "whatsapp_policy": {
                            "event": "campaign_interest_handoff_active",
                            "handoff_id": campaign_interest_handoff.get("id"),
                        }
                    },
                )
                payload = {
                    "answer": answer,
                    "confidence_score": 1.0,
                    "handoff_recommended": True,
                    "human_intervention_recommended": True,
                    "needs_human": True,
                    "handoff_reason": "campaign_interest_active",
                    "confidence_reason": "campaign_interest_handoff_active",
                }
                return payload if return_metadata else answer
            logger.info(
                "Campaign-interest handoff active but allowing normal routing | client_ref=%s | session_fp=%s",
                _safe_tail(client_id),
                _safe_hash(session_id),
            )

    if is_whatsapp and _is_whatsapp_handoff_request(message):
        handoff_info = _upsert_whatsapp_handoff(
            client_id=client_id,
            session_id=session_id,
            user_message=message,
            ai_message="",
            trigger="user_requested_human",
            reason="user_requested_human",
            language=lang,
        )
        answer = (
            _whatsapp_handoff_confirmation_message(lang)
            if handoff_info.get("handoff_id")
            else _scope_outside_message(lang)
        )
        save_history(
            client_id,
            session_id,
            "user",
            message,
            channel=channel,
            provider=provider,
        )
        save_history(
            client_id,
            session_id,
            "assistant",
            answer,
            channel=channel,
            provider=provider,
            metadata={
                "whatsapp_policy": {
                    "event": "explicit_handoff_request",
                    "handoff_id": handoff_info.get("handoff_id"),
                    "feature_enabled": bool(handoff_info.get("feature_enabled")),
                }
            },
        )
        payload = {
            "answer": answer,
            "confidence_score": 0.95,
            "handoff_recommended": bool(handoff_info.get("handoff_id")),
            "human_intervention_recommended": bool(handoff_info.get("handoff_id")),
            "needs_human": bool(handoff_info.get("handoff_id")),
            "handoff_reason": "user_requested_human" if handoff_info.get("handoff_id") else None,
            "confidence_reason": "whatsapp_explicit_handoff_request",
        }
        return payload if return_metadata else answer

    route = route_message(client_id, session_id, message, channel=channel)

    # route_message can return a direct user-facing blocked message.
    if route not in {"calendar", "rag"}:
        save_history(
            client_id,
            session_id,
            "user",
            message,
            channel=channel,
            provider=provider,
            source_type="appointment",
        )
        save_history(
            client_id,
            session_id,
            "assistant",
            str(route),
            channel=channel,
            provider=provider,
            source_type="appointment",
        )
        if return_metadata:
            return {
                "answer": str(route),
                "confidence_score": 0.95,
                "handoff_recommended": False,
                "human_intervention_recommended": False,
                "needs_human": False,
                "handoff_reason": None,
                "confidence_reason": "router_direct_message",
            }
        return route

    # 📅 Flujo de calendario
    if route == "calendar":
        print("📅 Routing → calendar")
        if _calendar_handler:
            answer = await _calendar_handler(client_id, message, session_id, channel, lang)
            save_history(
                client_id,
                session_id,
                "user",
                message,
                channel=channel,
                provider=provider,
                source_type="appointment",
            )
            save_history(
                client_id,
                session_id,
                "assistant",
                str(answer),
                channel=channel,
                provider=provider,
                source_type="appointment",
            )
            if return_metadata:
                return {
                    "answer": str(answer),
                    "confidence_score": 0.88,
                    "handoff_recommended": False,
                    "human_intervention_recommended": False,
                    "needs_human": False,
                    "handoff_reason": None,
                    "confidence_reason": "calendar_handler_response",
                }
            return answer
        calendar_unavailable = "🗓️ It seems you’d like to schedule an appointment, but this feature isn’t available yet."
        if return_metadata:
            return {
                "answer": calendar_unavailable,
                "confidence_score": 0.3,
                "handoff_recommended": True,
                "human_intervention_recommended": True,
                "needs_human": True,
                "handoff_reason": "calendar_handler_unavailable",
                "confidence_reason": "calendar_feature_unavailable",
            }
        return calendar_unavailable

    # 💬 Flujo RAG
    print("💬 Routing → RAG")
    base_message = [{"role": "user", "content": message}]

    if is_whatsapp:
        rag_payload = ask_question(
            base_message,
            client_id,
            session_id=session_id,
            channel=channel,
            provider=provider,
            return_metadata=True,
            persist_history=False,
        )
        if not isinstance(rag_payload, dict):
            rag_payload = {
                "answer": str(rag_payload or ""),
                "confidence_score": 0.5,
                "handoff_recommended": False,
                "human_intervention_recommended": False,
                "needs_human": False,
                "handoff_reason": None,
                "confidence_reason": "whatsapp_rag_non_metadata_payload",
            }

        answer = str(rag_payload.get("answer") or "")
        confidence_score = float(rag_payload.get("confidence_score") or 0.5)
        handoff_recommended = bool(rag_payload.get("handoff_recommended"))
        handoff_reason = rag_payload.get("handoff_reason")
        confidence_reason = str(rag_payload.get("confidence_reason") or "")

        assistant_metadata: dict[str, Any] = {
            "rag": {
                "confidence_score": confidence_score,
                "handoff_recommended": handoff_recommended,
                "handoff_reason": handoff_reason,
                "confidence_reason": confidence_reason,
            }
        }

        out_of_scope_reasons = {
            "rag_fallback_response",
            "retriever_returned_no_docs",
            "anti_hallucination_fallback",
        }
        is_out_of_scope = handoff_recommended and confidence_reason in out_of_scope_reasons

        if is_out_of_scope:
            if _last_assistant_was_scope_redirect(client_id, session_id):
                handoff_info = _upsert_whatsapp_handoff(
                    client_id=client_id,
                    session_id=session_id,
                    user_message=message,
                    ai_message=answer,
                    trigger="ai_out_of_scope_consecutive",
                    reason="out_of_scope_consecutive",
                    language=lang,
                )
                if handoff_info.get("handoff_id"):
                    answer = _whatsapp_handoff_confirmation_message(lang)
                    handoff_recommended = True
                    handoff_reason = "out_of_scope_consecutive"
                    confidence_reason = "whatsapp_auto_handoff_second_out_of_scope"
                    assistant_metadata["whatsapp_policy"] = {
                        "event": "auto_handoff_after_out_of_scope",
                        "handoff_id": handoff_info.get("handoff_id"),
                        "feature_enabled": bool(handoff_info.get("feature_enabled")),
                    }
                else:
                    answer = _scope_outside_message(lang)
                    handoff_recommended = False
                    handoff_reason = None
                    confidence_reason = "whatsapp_out_of_scope_handoff_unavailable"
                    assistant_metadata["whatsapp_policy"] = {
                        "event": "out_of_scope_handoff_unavailable",
                        "feature_enabled": bool(handoff_info.get("feature_enabled")),
                    }
            else:
                answer = _scope_redirect_message(lang)
                handoff_recommended = False
                handoff_reason = None
                confidence_reason = "whatsapp_out_of_scope_redirect"
                assistant_metadata["whatsapp_policy"] = {
                    "event": "out_of_scope_redirect",
                }

        if lang == "es" and answer and not str(answer).strip().endswith("."):
            answer = str(answer) + "."

        save_history(
            client_id,
            session_id,
            "user",
            message,
            channel=channel,
            provider=provider,
        )
        save_history(
            client_id,
            session_id,
            "assistant",
            answer,
            channel=channel,
            provider=provider,
            metadata=assistant_metadata,
        )

        payload = {
            "answer": answer,
            "confidence_score": confidence_score,
            "handoff_recommended": bool(handoff_recommended),
            "human_intervention_recommended": bool(handoff_recommended),
            "needs_human": bool(handoff_recommended),
            "handoff_reason": handoff_reason,
            "confidence_reason": confidence_reason,
        }
        return payload if return_metadata else answer

    answer = ask_question(
        base_message,
        client_id,
        session_id=session_id,
        channel=channel,
        provider=provider,
        return_metadata=return_metadata,
    )
    if return_metadata and isinstance(answer, dict):
        text = str(answer.get("answer") or "")
        if lang == "es" and text and not text.strip().endswith("."):
            answer["answer"] = text + "."
        return answer
    if lang == "es" and answer and not str(answer).strip().endswith("."):
        answer = str(answer) + "."
    return answer
