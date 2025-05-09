# api/chat_widget.py

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.utils.usage_limiter import check_and_increment_usage

router = APIRouter()

class ChatRequest(BaseModel):
    public_client_id: str
    message: str
    channel: str = "chat"

@router.post("/chat")
async def chat_widget(request: Request):
    try:
        print("📥 Petición recibida en /chat")

        body = await request.json()
        print("📦 Body recibido:", body)

        # Validar que los campos necesarios están presentes
        if "public_client_id" not in body or "message" not in body:
            print("❌ Faltan campos obligatorios en el body")
            raise HTTPException(status_code=400, detail="public_client_id y message son obligatorios")

        public_client_id = body["public_client_id"]
        message = body["message"]
        channel = body.get("channel", "chat")

        print(f"💬 [{channel}] Mensaje recibido: '{message}' (public_client_id: {public_client_id})")

        # Buscar client_id real en Supabase
        client_res = supabase.table("clients") \
            .select("id") \
            .eq("public_client_id", public_client_id) \
            .maybe_single() \
            .execute()

        if not client_res or not client_res.data:
            print(f"❌ Supabase no devolvió datos para public_client_id: {public_client_id}")
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        client_id = client_res.data["id"]
        print(f"✅ client_id encontrado: {client_id}")

        # Validar uso
        check_and_increment_usage(client_id, usage_type="messages_used")
        print(f"📊 Uso validado para client_id: {client_id}")

        # Ejecutar pipeline RAG
        print("🧠 Llamando a ask_question()...")
        answer = ask_question(message, client_id)
        print("✅ Respuesta generada por RAG:", answer)

        # Guardar en historial
        supabase.table("history").insert({
            "client_id": client_id,
            "question": message,
            "answer": answer,
            "channel": channel
        }).execute()

        print(f"📚 Guardado en historial para {client_id} (canal: {channel})")
        return {"answer": answer}

    except HTTPException as he:
        print(f"⚠️ Error controlado ({he.status_code}):", he.detail)
        raise he
    except Exception as e:
        print(f"❌ Error inesperado en /chat:", str(e))
        raise HTTPException(status_code=500, detail="Error al procesar el mensaje.")
