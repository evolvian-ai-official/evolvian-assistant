from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.assistant_rag.supabase_client import supabase
from modules.assistant_rag.rag_pipeline import ask_question
from utils.usage_limiter import check_and_increment_usage  # ✅

router = APIRouter()

class ChatRequest(BaseModel):
    client_id: str
    message: str
    channel: str = "chat"  # default si no se especifica

@router.post("/chat")
def chat_widget(request: ChatRequest):
    try:
        print(f"💬 [{request.channel}] {request.client_id}: {request.message}")

        # ✅ Validar uso antes de procesar
        check_and_increment_usage(request.client_id, usage_type="messages_used")

        # Generar respuesta con RAG
        answer = ask_question(request.message, request.client_id)

        # Guardar en historial
        supabase.table("history").insert({
            "client_id": request.client_id,
            "question": request.message,
            "answer": answer,
            "channel": request.channel
        }).execute()

        print(f"✅ Guardado en history para {request.client_id} (canal: {request.channel})")

        return {"answer": answer}

    except HTTPException as he:
        raise he  # ❗ Importante para no ocultar el error 403
    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar el mensaje.")
