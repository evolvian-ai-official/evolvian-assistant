from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from datetime import datetime
import re

from api.config import config
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.calendar.google_calendar import get_availability_from_google_calendar
from api.modules.calendar_logic import save_appointment_if_valid

router = APIRouter()

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."
MAX_DAILY_MESSAGES_INTERNAL = 1000  # 💡 Límite diario solo para Evolvian Support Bot

def is_availability_request(text: str) -> bool:
    text = text.lower()
    keywords = [
        "horarios disponibles", "disponibilidad", "agendar", 
        "citas disponibles", "cuándo puedo", "calendar disponible"
    ]
    return any(kw in text for kw in keywords)

@router.post("/ask")
async def ask(question: str = Form(...), client_id: str = Form(...)):
    try:
        print(f"❓ Pregunta recibida: '{question}' para cliente: {client_id}")

        # 🔐 Lógica especial para Evolvian Support Bot
        if client_id == "evolvian-internal":
            today = datetime.utcnow().date().isoformat()
            usage_res = supabase.table("chat_usage")\
                .select("count")\
                .eq("client_id", client_id)\
                .eq("date", today)\
                .single()\
                .execute()

            if usage_res.error:
                print(f"⚠️ Error al consultar uso interno: {usage_res.error}")
                return JSONResponse(status_code=500, content={"error": "Error al validar el uso del asistente."})

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

        # 🧠 Detección de disponibilidad
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
            return JSONResponse(content={"answer": answer})

        # 📌 Agendamiento directo con fecha detectada automáticamente (más flexible)
        print("📥 Revisando si el mensaje contiene fecha ISO...")
        print(f"🔍 Mensaje recibido: {question}")

        iso_match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:-\d{2}:\d{2})?", question)
        if iso_match:
            try:
                raw_datetime = iso_match.group()
                print(f"✅ Fecha encontrada: {raw_datetime}")

                scheduled_time = datetime.fromisoformat(raw_datetime)

                success = save_appointment_if_valid(
                    client_id=client_id,
                    scheduled_time_str=scheduled_time.isoformat()
                )

                return JSONResponse(content={"answer": success})

            except Exception as e:
                print(f"❌ Error al intentar agendar: {e}")
                return JSONResponse(content={"answer": f"❌ Error al intentar agendar la cita: {e}"})
        else:
            print("❌ No se encontró una fecha válida en el mensaje.")

        # 🧠 Prompt personalizado
        settings_res = supabase.table("client_settings")\
            .select("custom_prompt")\
            .eq("client_id", client_id)\
            .single()\
            .execute()

        if settings_res.error:
            print(f"⚠️ Error al obtener el prompt: {settings_res.error}")
            prompt = DEFAULT_PROMPT
        else:
            prompt = settings_res.data.get("custom_prompt", DEFAULT_PROMPT) if settings_res.data else DEFAULT_PROMPT

        # 🤖 RAG
        response = ask_question(question, client_id, prompt=prompt)

        return JSONResponse(content={"answer": response})

    except Exception as e:
        print(f"❌ Error procesando pregunta: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
