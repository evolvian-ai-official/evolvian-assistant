# api/chat_widget.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.assistant_rag.rag_pipeline import ask_question
from utils.usage_limiter import check_and_increment_usage

router = APIRouter()

class ChatRequest(BaseModel):
    public_client_id: str
    message: str
    channel: str = "chat"  # default si no se especifica

@router.post("/chat")
def chat_widget(request: ChatRequest):
    try:
        print(f"💬 [{request.channel}] {request.public_client_id}: {request.message}")

        # 🚨 Buscar client_id real usando public_client_id
        client_res = supabase.table("clients") \
            .select("id") \
            .eq("public_client_id", request.public_client_id) \
            .maybe_single() \
            .execute()

        if not client_res or not client_res.data:
            print(f"❌ Supabase no devolvió datos para public_client_id: {request.public_client_id}")
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        client_id = client_res.data["id"]
        print(f"✅ client_id encontrado: {client_id}")

        # ✅ Validar uso antes de procesar
        check_and_increment_usage(client_id, usage_type="messages_used")

        # 🧠 Ejecutar pipeline RAG (con signed URLs)
        answer = ask_question(request.message, client_id)

        # 💾 Guardar en historial
        supabase.table("history").insert({
            "client_id": client_id,
            "question": request.message,
            "answer": answer,
            "channel": request.channel
        }).execute()

        print(f"✅ Guardado en history para {client_id} (canal: {request.channel})")
        return {"answer": answer}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar el mensaje.")
