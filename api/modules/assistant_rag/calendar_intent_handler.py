# =====================================================
# 📅 calendar_intent_handler.py — Production-ready LLM-only handler
# =====================================================
import json
import logging
import re
from datetime import datetime, timedelta, time as dtime
from api.modules.assistant_rag.prompts.calendar_prompt import get_calendar_prompt
from api.modules.assistant_rag.llm import openai_chat
from api.modules.assistant_rag.supabase_client import supabase

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
    """
    Detecta confirmaciones aunque estén dentro de frases largas.
    """
    s = msg.strip().lower()
    yes_keywords = [
        "si", "sí", "yes", "yep", "sure", "ok", "okay", "vale", "confirmo",
        "confirmar", "confirmada", "reserva", "book", "schedule", "agendar", "proceed"
    ]
    for kw in yes_keywords:
        if kw in s:
            return True
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


def _resolve_date_token(text: str) -> str | None:
    s = text.lower()
    now = datetime.now()

    if "hoy" in s or "today" in s:
        return now.strftime("%Y-%m-%d")
    if "mañana" in s or "manana" in s or "tomorrow" in s:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    for wd, idx in WEEKDAYS_ES.items():
        if wd in s:
            return _next_weekday(now, idx).strftime("%Y-%m-%d")
    for wd, idx in WEEKDAYS_EN.items():
        if wd in s:
            return _next_weekday(now, idx).strftime("%Y-%m-%d")

    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", s)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        try:
            return datetime(now.year, mo, d).strftime("%Y-%m-%d")
        except Exception:
            return None

    m = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\b", s)
    if m:
        d = int(m.group(1))
        mo = MONTHS_ES.get(m.group(2).lower())
        if mo:
            try:
                return datetime(now.year, mo, d).strftime("%Y-%m-%d")
            except Exception:
                return None

    m = re.search(r"\b([a-z]+)\s+(\d{1,2})\b", s)  # November 14
    if m and m.group(1).lower() in MONTHS_EN:
        mo = MONTHS_EN[m.group(1).lower()]
        d = int(m.group(2))
        try:
            return datetime(now.year, mo, d).strftime("%Y-%m-%d")
        except Exception:
            return None

    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+([a-z]+)\b", s)  # 14th of November
    if m and m.group(2).lower() in MONTHS_EN:
        d = int(m.group(1))
        mo = MONTHS_EN[m.group(2).lower()]
        try:
            return datetime(now.year, mo, d).strftime("%Y-%m-%d")
        except Exception:
            return None

    return None


def _extract_times_from_text(text: str) -> list[str]:
    times = []
    for a, _ in RANGE_RE.findall(text):
        times.append(a)
    if not times:
        for m in TIME_RE.findall(text):
            times.append(m.strip())
    return times


def _looks_like_name(message: str) -> bool:
    s = message.strip()
    low = s.lower()
    if any(ch.isdigit() for ch in s) or "@" in low:
        return False
    if low in YES_TOKENS or low in NO_TOKENS:
        return False
    forbidden = [
        "horario",
        "disponible",
        "agendar",
        "reservar",
        "cita",
        "llamada",
        "dame",
        "book",
        "schedule",
        "available",
        "options",
        "opciones",
        "number",
        "número",
        "numero",
        "option",
    ]
    if any(w in low for w in forbidden):
        return False
    if not re.search(r"[a-záéíóúñ]", low):
        return False
    return len(s.split()) >= 2


def _extract_selection_index(msg: str) -> int | None:
    low = msg.lower().strip()
    m = re.search(r"(?:^|\s)(?:option|opcion|opción|number|número|numero|#)?\s*(\d{1,2})(?:[\.\)]|$|\s)", low)
    if m:
        try:
            return int(m.group(1)) - 1
        except Exception:
            return None
    if re.fullmatch(r"\d{1,2}", low):
        return int(low) - 1
    return None


def _load_settings(client_id: str) -> dict | None:
    try:
        res = supabase.table("calendar_settings").select("*").eq("client_id", client_id).limit(1).execute()
        return res.data[0] if res and res.data else None
    except Exception as e:
        logger.warning(f"⚠️ Could not load calendar_settings: {e}")
        return None


def _validate_slot(settings: dict, iso_str: str) -> tuple[bool, str | None]:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", ""))
    except Exception:
        return False, "Fecha/hora inválida."

    now = datetime.now()
    min_h = int(settings.get("min_notice_hours") or 0)
    if dt < now + timedelta(hours=min_h):
        return False, f"Debe respetar aviso mínimo de {min_h} horas."

    start = settings.get("start_time")
    end = settings.get("end_time")
    if start and end:
        s_h, s_m = map(int, start.split(":"))
        e_h, e_m = map(int, end.split(":"))
        if not (dtime(s_h, s_m) <= dtime(dt.hour, dt.minute) <= dtime(e_h, e_m)):
            return False, f"Fuera del horario laboral ({start}–{end})."

    return True, None


def _book_appointment(client_id: str, collected: dict) -> bool:
    try:
        payload = {
            "client_id": client_id,
            "user_email": collected.get("user_email"),
            "user_name": collected.get("user_name"),
            "scheduled_time": collected.get("scheduled_time"),
        }
        supabase.table("appointments").insert(payload).execute()
        return True
    except Exception as e:
        logger.error(f"❌ Error inserting appointment: {e}")
        return False


def _extract_fields(message: str, state: dict) -> dict:
    msg = message.strip()
    low = msg.lower()
    EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,}")

    out = {}

    m = EMAIL_RE.search(msg)
    if m:
        out["user_email"] = m.group(0)

    m = PHONE_RE.search(msg)
    if m:
        out["user_phone"] = re.sub(r"\s+", "", m.group(0))

    if _looks_like_name(msg):
        out["user_name"] = msg.title()

    if state.get("proposed_slots"):
        idx = _extract_selection_index(msg)
        if idx is not None and 0 <= idx < len(state["proposed_slots"]):
            out["scheduled_time"] = state["proposed_slots"][idx]["start_iso"]

    date_iso = _resolve_date_token(low)
    if date_iso:
        out["scheduled_date_hint"] = date_iso

    times = _extract_times_from_text(msg)
    if times:
        out["scheduled_time_hint"] = times[0]

    if out.get("scheduled_date_hint") and out.get("scheduled_time_hint"):
        out["scheduled_time"] = f"{out['scheduled_date_hint']}T{_normalize_time_str(out['scheduled_time_hint'])}:00"

    return out


def handle_calendar_intent(client_id: str, message: str, session_id: str, channel: str, lang: str):
    logger.info(f"🧭 [LLM-Only Mode] Calendar intent for client_id={client_id}")

    # ============================================================
    # 🧠 Cargar estado previo de la conversación
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

    state.setdefault("intent", "calendar")
    state.setdefault("status", "collecting")
    state.setdefault("collected", {})
    collected = state["collected"]

    # ============================================================
    # 🧩 Extraer campos del mensaje (nombre, email, hora, fecha…)
    # ============================================================
    new_data = _extract_fields(message, state)
    for k, v in new_data.items():
        if v:
            collected[k] = v

    if "scheduled_time" not in collected and collected.get("scheduled_time_hint"):
        date_hint = collected.get("scheduled_date_hint") or state.get("last_date_hint")
        if date_hint:
            collected["scheduled_time"] = f"{date_hint}T{_normalize_time_str(collected['scheduled_time_hint'])}:00"

    if collected.get("scheduled_date_hint"):
        state["last_date_hint"] = collected["scheduled_date_hint"]

    # ============================================================
    # ⚙️ Cargar reglas de configuración del calendario
    # ============================================================
    settings = _load_settings(client_id)

    # ============================================================
    # 📅 Confirmar cita si ya hay horario propuesto
    # ============================================================
    if collected.get("scheduled_time"):
        if state.get("status") == "pending_confirmation" and _is_yes(message):
            if settings:
                ok, reason = _validate_slot(settings, collected["scheduled_time"])
                if not ok:
                    reply = f"{'⚠️' if lang == 'es' else '⚠️'} " + (
                        f"Ese horario no cumple reglas: {reason}. "
                        if lang == "es"
                        else f"That time violates rules: {reason}. "
                    )
                    reply += (
                        "¿Te propongo opciones válidas?"
                        if lang == "es"
                        else "Shall I propose valid options?"
                    )
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
                    return reply

            # ====================================================
            # 💾 Registrar cita en appointments
            # ====================================================
            if _book_appointment(client_id, collected):
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

                # ====================================================
                # 🚀 Post-booking pipeline (Calendar + Emails)
                # ====================================================
                try:
                    import datetime, sys
                    from pathlib import Path

                    # 🧭 Asegurar que la raíz del proyecto esté en el path
                    BASE_DIR = Path(__file__).resolve().parents[2]
                    if str(BASE_DIR) not in sys.path:
                        sys.path.append(str(BASE_DIR))
                        logger.info(f"🧩 Added BASE_DIR to sys.path: {BASE_DIR}")

                    # 📦 Importar módulos reales
                    from api.modules.calendar.schedule_event import schedule_event
                    from api.modules.calendar.send_confirmation_email import send_confirmation_email
                    from api.modules.calendar.notify_business_owner import notify_business_owner

                    logger.info("📤 Starting post-booking pipeline (email + calendar)...")

                    # 🗓️ Crear evento en Google Calendar
                    try:
                        payload = {
                            "client_id": client_id,
                            "start": collected["scheduled_time"],
                            "user_email": collected.get("user_email"),
                            "user_name": collected.get("user_name"),
                        }
                        schedule_event(payload)
                        logger.info("✅ Google Calendar event scheduled successfully.")
                    except Exception as e:
                        logger.error(f"❌ Error creating Google Calendar event: {e}")

                    # 📧 Enviar correos
                    try:
                        dt = datetime.datetime.fromisoformat(collected["scheduled_time"])
                        date_str = dt.strftime("%Y-%m-%d")
                        hour_str = dt.strftime("%H:%M")

                        if collected.get("user_email"):
                            send_confirmation_email(
                                collected["user_email"], date_str, hour_str
                            )
                            logger.info(
                                f"✅ Confirmation email sent to {collected['user_email']}"
                            )

                        notify_business_owner(
                            client_id,
                            collected["scheduled_time"],
                            collected.get("user_email"),
                            collected.get("user_name"),
                            collected.get("user_phone"),
                        )
                        logger.info("✅ Business owner notification sent successfully.")
                    except Exception as e:
                        logger.error(
                            f"❌ Error sending confirmation/notification emails: {e}"
                        )

                except Exception as e:
                    logger.error(f"❌ Post-booking pipeline general error: {e}")

                return (
                    "✅ Tu cita ha sido registrada. (Recibirás confirmación pronto.)"
                    if lang == "es"
                    else "✅ Your appointment has been registered. (You’ll receive a confirmation soon.)"
                )
            else:
                return (
                    "❌ No pude registrar la cita. Intenta con otro horario."
                    if lang == "es"
                    else "❌ I couldn't register the appointment. Try another time."
                )

    # ============================================================
    # 🔁 Si aún está recopilando datos, actualizar estado
    # ============================================================
    if state.get("status") == "collecting":
        state["status"] = "pending_confirmation"

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
    # 💬 Generar respuesta LLM si no hay cita confirmada
    # ============================================================
    calendar_prompt = get_calendar_prompt(client_id, collected)
    if not calendar_prompt:
        return "⚠️ No hay configuración activa de calendario para este cliente."

    messages = [
        {"role": "system", "content": calendar_prompt},
        {"role": "user", "content": message},
    ]

    try:
        ai_response = openai_chat(messages, temperature=0.35)
    except Exception as e:
        logger.error(f"❌ Error invoking LLM calendar prompt: {e}")
        return (
            "❌ Hubo un problema con el asistente de calendario."
            if lang == "es"
            else "❌ There was a problem with the calendar assistant."
        )

    # ============================================================
    # 📅 Extraer posibles horarios sugeridos por el LLM
    # ============================================================
    proposed = []
    date_from_llm = _resolve_date_token(ai_response.lower())
    if date_from_llm:
        state["last_date_hint"] = date_from_llm
        collected.setdefault("scheduled_date_hint", date_from_llm)

    lines = [ln.strip() for ln in ai_response.splitlines() if ln.strip()]
    for ln in lines:
        rng = RANGE_RE.search(ENUM_PREFIX_RE.sub("", ln))
        if rng:
            base_date = collected.get("scheduled_date_hint") or date_from_llm
            start_hhmm = _normalize_time_str(rng.group(1))
            end_hhmm = _normalize_time_str(rng.group(2))
            if base_date:
                proposed.append(
                    {
                        "start_iso": f"{base_date}T{start_hhmm}:00",
                        "end_iso": f"{base_date}T{end_hhmm}:00",
                    }
                )

    # ============================================================
    # 🕓 Si hay horarios válidos, mostrarlos al usuario
    # ============================================================
    if proposed:
        state["proposed_slots"] = proposed
        try:
            supabase.table("conversation_state").upsert(
                {"client_id": client_id, "session_id": session_id, "state": state},
                on_conflict="client_id,session_id",
            ).execute()
        except Exception as e:
            logger.warning(f"⚠️ Could not save proposed slots: {e}")

        reply_lines = []
        for i, slot in enumerate(proposed, 1):
            start_iso = slot.get("start_iso")
            end_iso = slot.get("end_iso")
            if start_iso and end_iso:
                t_start = start_iso.split("T")[1][:5]
                t_end = end_iso.split("T")[1][:5]
                reply_lines.append(f"{i}. {t_start} - {t_end}")

        reply = (
            f"Para {base_date}, aquí tienes algunas opciones disponibles:\n\n"
            + "\n".join(reply_lines)
            if lang == "es"
            else f"For {base_date}, here are some available options:\n\n"
            + "\n".join(reply_lines)
        )
        return reply

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
