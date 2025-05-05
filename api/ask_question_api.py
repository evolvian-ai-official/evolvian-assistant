# api/ask_question_api.py

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from api.config import config

from api.modules.assistant_rag.rag_pipeline import ask_question
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."
MAX_DAILY_MESSAGES_INTERNAL = 1000  # 💡 Límite diario solo para Evolvian Support Bot

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

            messages_today = usage_res.data.get("count", 0) if usage_res.data else 0

            if messages_today >= MAX_DAILY_MESSAGES_INTERNAL:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Límite diario de mensajes alcanzado para el asistente de soporte interno."}
                )

            # Si ya existe, actualizar; si no, insertar
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

        # 🧠 Obtener prompt personalizado (o usar default)
        settings_res = supabase.table("client_settings")\
            .select("custom_prompt")\
            .eq("client_id", client_id)\
            .single()\
            .execute()

        prompt = settings_res.data.get("custom_prompt", DEFAULT_PROMPT) if settings_res.data else DEFAULT_PROMPT

        # 🤖 Ejecutar pipeline RAG
        response = ask_question(question, client_id, prompt=prompt)

        return JSONResponse(content={"answer": response})

    except Exception as e:
        print(f"❌ Error procesando pregunta: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
