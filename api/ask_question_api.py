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
async def ask(question: str = Form(...), client_id: str = Form(...), session_id: str = Form(None)):
    """
    Endpoint principal de conversación.
    Incluye:
      - Límite de mensajes interno (para Evolvian Support)
      - Detección de disponibilidad y agendamiento
      - Ejecución del pipeline RAG con memoria conversacional
    """
    try:
        print(f"❓ Pregunta recibida: '{question}' para cliente: {client_id}")

        # 🔐 Lógica especial para el asistente interno de Evolvian
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
                print(f"⚠️ Error al consultar uso interno: {usage_res.error}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Error al validar el uso del asistente."}
                )

            messages_today = usage_res.data.get("count", 0) if usage_res.data else 0

            if messages_today >= MAX_DAILY_MESSAGES_INTERNAL:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Límite diario de mensajes alcanzado para el asistente de soporte interno."}
                )

            if usage_res.data:
                supabase.table("chat_usage").update({
                    "count": messages_today + 1
                }).eq("client_id", client_id).eq("date", today).execute()
            else:
                supabase.table("chat_usage").insert({
                    "client_id": client_id,
                    "date": today,
                    "count": 1
                }).execute()

        # 🧠 Detección de solicitudes de disponibilidad
        if is_availability_request(question):
            calendar_res = get_availability_from_google_calendar(client_id)
            slots = calendar_res.get("available_slots", [])
            if slots:
                formatted_slots = "\n".join(
                    [f"- {datetime.fromisoformat(slot).strftime('%A %d de %B a las %H:%M')}" for slot in slots]
                )
                answer = f"📅 Aquí tienes algunos horarios disponibles:\n\n{formatted_slots}"
            else:
                answer = calendar_res.get("message", "No se encontraron horarios disponibles.")
            
            # Guardamos en historial
            session_id = session_id or str(uuid.uuid4())
            save_history(client_id, session_id, "user", question, channel="chat")
            save_history(client_id, session_id, "assistant", answer, channel="chat")

            return JSONResponse(content={"answer": answer, "session_id": session_id})

        # 📌 Detección de formato de fecha para agendamiento
        iso_match = re.search(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:-\d{2}:\d{2})?", question
        )
        if iso_match:
            try:
                raw_datetime = iso_match.group()
                scheduled_time = datetime.fromisoformat(raw_datetime)

                success = save_appointment_if_valid(
                    client_id=client_id,
                    scheduled_time_str=scheduled_time.isoformat(),
                )

                session_id = session_id or str(uuid.uuid4())
                save_history(client_id, session_id, "user", question, channel="chat")
                save_history(client_id, session_id, "assistant", success, channel="chat")

                return JSONResponse(content={"answer": success, "session_id": session_id})

            except Exception as e:
                print(f"❌ Error al intentar agendar: {e}")
                return JSONResponse(
                    content={"answer": f"❌ Error al intentar agendar la cita: {e}"}
                )

        # 🧩 Crear o recuperar sesión
        session_id = session_id or str(uuid.uuid4())

        # 🧠 Recuperar últimos mensajes del historial para memoria conversacional
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
        print(f"🧩 Contexto recuperado: {len(context_messages)} mensajes previos")

        # Combinar contexto con nueva pregunta
        message_payload = context_messages + [{"role": "user", "content": question}]

        # Guardar mensaje del usuario
        save_history(client_id, session_id, "user", question, channel="chat")

        # 🤖 RAG principal con rol + contenido (memoria de conversación)
        response = ask_question(message_payload, client_id, session_id=session_id)

        # Guardar respuesta del asistente
        save_history(client_id, session_id, "assistant", response, channel="chat")

        return JSONResponse(content={"answer": response, "session_id": session_id})

    except Exception as e:
        logging.exception(f"❌ Error procesando pregunta: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
