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
import json
import re
from typing import Any, Dict, Optional
import traceback

# === Dependencias del proyecto ===
from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.assistant_rag.rag_pipeline import ask_question

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
    from api.modules.assistant_rag.intent_detector import detect_intent_to_schedule as _detect_intent_to_schedule
except Exception:
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
    "horario", "book", "schedule", "appointment", "slot", "slots"
}

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
    t = (message or "").lower()
    return any(k in t for k in AGENDA_KEYWORDS)

def detect_intent_to_schedule(message: str) -> bool:
    """Wrapper: detector avanzado o fallback local."""
    if _detect_intent_to_schedule:
        try:
            return bool(_detect_intent_to_schedule(message))
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

def upsert_state(client_id: str, session_id: str, state: Dict) -> None:
    try:
        supabase.table(CS_TABLE).upsert(
            {
                "client_id": client_id,
                "session_id": session_id,
                "state": state or {},
            },
            on_conflict="client_id,session_id",
        ).execute()
    except Exception as e:
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
    SCHEDULING_HINTS = {
        "agendar", "reservar", "reagendar", "cita", "citas", "sesion", "sesión",
        "book", "schedule", "appointment", "reschedule", "slot", "slots",
        "horario", "horarios", "disponibilidad", "availability",
    }

    # Priorizar preguntas comerciales simples (planes/precios) para evitar falsos positivos.
    if any(k in text for k in PRICING_HINTS) and not any(k in text for k in SCHEDULING_HINTS):
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
        "precio", "precios", "cuánto", "cuanto", "coste", "planes"
    }

    def user_wants_to_exit_calendar(msg: str) -> bool:
        t = (msg or "").lower()
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
    if active_intent == "calendar" and status in ["collecting", "pending_confirmation"]:
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
