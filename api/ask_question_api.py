from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from datetime import datetime
import re
import uuid
import logging

from api.modules.assistant_rag.rag_pipeline import ask_question
from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.calendar.google_calendar import get_availability_from_google_calendar
from api.modules.calendar_logic import save_appointment_if_valid

router = APIRouter()

MAX_DAILY_MESSAGES_INTERNAL = 1000  # 💡 Límite diario solo para Evolvian Support Bot


def is_availability_request(text: str) -> bool:
    """Detecta si el texto del usuario está pidiendo disponibilidad."""
    text = text.lower()
    keywords = [
        "horarios disponibles", "disponibilidad", "agendar",
        "citas disponibles", "cuándo puedo", "calendar disponible"
    ]
    return any(kw in text for kw in keywords)


@router.post("/ask")
async def ask(
    question: str = Form(...),
    client_id: str = Form(...),
    session_id: str = Form(None),
):
    """
    Endpoint principal de conversación (PRODUCCIÓN).

    Responsabilidades:
    - Validar límites (solo evolvian-internal)
    - Detectar flujos especiales (calendar / appointment)
    - Recuperar contexto conversacional
    - Delegar TODA la lógica de RAG + historial a ask_question()
    """

    try:
        logging.info(f"❓ Pregunta recibida | client={client_id} | text='{question}'")

        # =====================================================
        # 🔐 Límite diario SOLO para asistente interno Evolvian
        # =====================================================
        if client_id == "evolvian-internal":
            today = datetime.utcnow().date().isoformat()

            usage_res = (
                supabase.table("chat_usage")
                .select("count")
                .eq("client_id", client_id)
                .eq("date", today)
                .single()
                .execute()
            )

            if usage_res.error:
                logging.error(f"❌ Error validando uso interno: {usage_res.error}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Error al validar el uso del asistente."},
                )

            messages_today = usage_res.data.get("count", 0) if usage_res.data else 0

            if messages_today >= MAX_DAILY_MESSAGES_INTERNAL:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Límite diario de mensajes alcanzado para el asistente interno."
                    },
                )

            # Incrementar contador diario
            if usage_res.data:
                supabase.table("chat_usage").update(
                    {"count": messages_today + 1}
                ).eq("client_id", client_id).eq("date", today).execute()
            else:
                supabase.table("chat_usage").insert(
                    {"client_id": client_id, "date": today, "count": 1}
                ).execute()

        # =====================================================
        # 🧠 Flujo especial: disponibilidad de calendario
        # (NO pasa por RAG)
        # =====================================================
        if is_availability_request(question):
            session_id = session_id or str(uuid.uuid4())

            calendar_res = get_availability_from_google_calendar(client_id)
            slots = calendar_res.get("available_slots", [])

            if slots:
                formatted_slots = "\n".join(
                    f"- {datetime.fromisoformat(slot).strftime('%A %d de %B a las %H:%M')}"
                    for slot in slots
                )
                answer = f"📅 Aquí tienes algunos horarios disponibles:\n\n{formatted_slots}"
            else:
                answer = calendar_res.get(
                    "message", "No se encontraron horarios disponibles."
                )

            # 🔒 Historial SOLO aquí (flujo alterno)
            save_history(client_id, session_id, "user", question, channel="chat")
            save_history(client_id, session_id, "assistant", answer, channel="chat")

            return JSONResponse(content={"answer": answer, "session_id": session_id})

        # =====================================================
        # 📌 Flujo especial: agendamiento directo por ISO datetime
        # =====================================================
        iso_match = re.search(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:-\d{2}:\d{2})?",
            question,
        )

        if iso_match:
            session_id = session_id or str(uuid.uuid4())

            try:
                scheduled_time = datetime.fromisoformat(iso_match.group())

                result = save_appointment_if_valid(
                    client_id=client_id,
                    scheduled_time_str=scheduled_time.isoformat(),
                )

                save_history(client_id, session_id, "user", question, channel="chat")
                save_history(client_id, session_id, "assistant", result, channel="chat")

                return JSONResponse(
                    content={"answer": result, "session_id": session_id}
                )

            except Exception as e:
                logging.exception("❌ Error al intentar agendar cita")
                return JSONResponse(
                    content={
                        "answer": "❌ No fue posible agendar la cita. Intenta nuevamente."
                    }
                )

        # =====================================================
        # 🧩 Flujo normal → RAG
        # =====================================================
        session_id = session_id or str(uuid.uuid4())

        # Recuperar contexto conversacional (solo lectura)
        context_res = (
            supabase.table("history")
            .select("role, content")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(6)
            .execute()
        )

        context_messages = context_res.data or []
        logging.info(
            f"🧩 Contexto cargado | mensajes_previos={len(context_messages)}"
        )

        message_payload = context_messages + [
            {"role": "user", "content": question}
        ]

        # ⚠️ HISTORIAL SE GUARDA EXCLUSIVAMENTE EN ask_question()
        response = ask_question(
            messages=message_payload,
            client_id=client_id,
            session_id=session_id,
        )

        return JSONResponse(
            content={"answer": response, "session_id": session_id}
        )

    except Exception as e:
        logging.exception("❌ Error inesperado en /ask")
        return JSONResponse(
            status_code=500,
            content={"error": "Error interno procesando la solicitud."},
        )
