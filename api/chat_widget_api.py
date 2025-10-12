from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
import logging
import uuid
import re

from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.utils.usage_limiter import check_and_increment_usage

router = APIRouter()

# 🔹 Input model
class ChatRequest(BaseModel):
    public_client_id: str
    session_id: str
    message: str
    channel: str = "chat"

# 🔒 Safely map public_client_id → client_id
def get_client_id_from_public_client_id(public_client_id: str) -> str:
    """Fetch client_id from Supabase using public_client_id."""
    try:
        response = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", public_client_id)
            .execute()
        )
        if not response.data or len(response.data) == 0:
            logging.error(f"❌ No client found for public_client_id={public_client_id}")
            raise ValueError("Client not found for provided public_client_id")

        client_id = response.data[0]["id"]
        uuid.UUID(client_id)  # ensure it's a valid UUID
        return client_id

    except Exception as e:
        logging.exception(f"🔥 Error resolving client_id for public_client_id={public_client_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid or missing client mapping for {public_client_id}")

# 🌍 Detect message language (simple heuristic)
def detect_language(text: str) -> str:
    """
    Detects whether the text is Spanish or English based on common words and characters.
    Returns 'es' or 'en'.
    """
    text_lower = text.lower()

    # Common Spanish signals
    spanish_words = [
        "hola", "gracias", "por favor", "necesito", "quiero", "cómo", "cuál",
        "dónde", "porque", "dame", "tengo", "plan", "ayuda", "mensaje", "precio",
        "cuánto", "qué", "cuando", "cuantos", "favor", "contacto", "correo", "whatsapp"
    ]

    # If special characters exist
    if any(c in text_lower for c in "áéíóúñ¿¡"):
        return "es"

    # If Spanish words are detected
    if any(word in text_lower for word in spanish_words):
        return "es"

    # English default (fallback)
    return "en"


# 🔹 Main chat endpoint
@router.post("/chat")
async def chat_widget(request: Request):
    try:
        print("📥 Incoming request to /chat")

        body = await request.json()
        print("📦 Received body:", body)

        required_fields = ["public_client_id", "session_id", "message"]
        if not all(field in body for field in required_fields):
            raise HTTPException(status_code=400, detail="Missing required fields: public_client_id, session_id, message")

        public_client_id = body["public_client_id"]
        session_id = body["session_id"]
        message = body["message"]
        channel = body.get("channel", "chat")

        print(f"💬 [{channel}] Message: '{message}' (public_client_id: {public_client_id}, session_id: {session_id})")

        # Get actual client_id
        client_id = get_client_id_from_public_client_id(public_client_id)
        print(f"✅ client_id resolved: {client_id}")

        # Validate plan usage
        check_and_increment_usage(client_id, usage_type="messages_used")

        # Count messages for this session
        history_count_res = (
            supabase.table("history")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .execute()
        )
        total_messages = len(history_count_res.data or [])
        print(f"💬 Total messages in session {session_id}: {total_messages}")

        # 🔒 Session limit
        MAX_MESSAGES_PER_SESSION = 24
        if total_messages >= MAX_MESSAGES_PER_SESSION * 2:  # user+assistant pairs
            user_lang = detect_language(message)
            print(f"🌍 Detected language: {user_lang}")

            limit_messages = {
                "en": "If you need more help, please contact us by email or WhatsApp. 💬",
                "es": "Si necesitas más ayuda, contáctanos por correo o WhatsApp. 💬"
            }

            limit_message = limit_messages.get(user_lang, limit_messages["en"])
            save_history(client_id, session_id, "assistant", limit_message, channel)
            return {"answer": limit_message, "session_id": session_id, "limit_reached": True}

        # Retrieve recent history
        history_res = (
            supabase.table("history")
            .select("role, content")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(6)
            .execute()
        )
        history_messages = [
            {"role": h["role"], "content": h["content"]}
            for h in (history_res.data or [])
        ]

        # Add current message
        history_messages.append({"role": "user", "content": message})

        # 🧠 Call RAG pipeline
        answer = ask_question(history_messages, client_id, session_id=session_id)
        print("✅ Generated answer:", answer)

        # 💾 Save history
        save_history(client_id, session_id, "user", message, channel)
        save_history(client_id, session_id, "assistant", answer, channel)

        return {"answer": answer, "session_id": session_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception("❌ Unexpected error in /chat")
        raise HTTPException(status_code=500, detail="Error processing the message.")

# 🔹 Serve widget HTML
@router.get("/chat-widget", response_class=HTMLResponse)
def serve_chat_widget(public_client_id: str):
    try:
        client_id = get_client_id_from_public_client_id(public_client_id)
        html_path = Path("dist/chat-widget.html")
        if not html_path.exists():
            raise HTTPException(status_code=500, detail="Widget HTML file not found")
        return HTMLResponse(content=html_path.read_text(), status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception("❌ Unexpected error in /chat-widget")
        raise HTTPException(status_code=500, detail="Error loading widget.")
