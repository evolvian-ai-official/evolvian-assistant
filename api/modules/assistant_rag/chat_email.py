from fastapi import APIRouter, HTTPException, Request
import logging
import uuid
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase, save_history
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.utils.usage_limiter import check_and_increment_usage

router = APIRouter()


# 🔹 Modelo de entrada
class EmailChatRequest(BaseModel):
    from_email: str
    subject: str | None = None
    message: str


# 🔍 Obtener client_id desde la tabla de canales
def get_client_id_from_email(email: str) -> str:
    try:
        res = (
            supabase.table("channels")
            .select("client_id")
            .eq("type", "email")
            .eq("value", email)
            .maybe_single()
            .execute()
        )
        if res and res.data:
            return res.data["client_id"]

        logging.warning(f"⚠️ No se encontró client_id para el correo {email}")
        raise HTTPException(status_code=404, detail="Email channel not linked to any client.")
    except Exception as e:
        logging.error(f"❌ Error obteniendo client_id desde email {email}: {e}")
        raise HTTPException(status_code=500, detail="Error resolving client_id for email.")


# 🌍 Detección simple de idioma
def detect_language(text: str) -> str:
    text_lower = text.lower()
    spanish_signals = ["hola", "gracias", "por favor", "ayuda", "plan", "precio", "cuánto", "quiero", "necesito"]
    if any(c in text_lower for c in "áéíóúñ¿¡") or any(w in text_lower for w in spanish_signals):
        return "es"
    return "en"


# 📩 Endpoint principal — igual que chat widget, pero adaptado al correo
@router.post("/chat_email")
async def chat_email(request: Request):
    try:
        body = await request.json()
        logging.info(f"📩 Email entrante detectado de {body.get('from_email')}")

        # Validar campos requeridos
        required_fields = ["from_email", "message"]
        if not all(f in body for f in required_fields):
            raise HTTPException(status_code=400, detail="Missing required fields: from_email, message")

        from_email = body["from_email"]
        message = body["message"].strip()
        subject = body.get("subject", "")
        session_id = str(uuid.uuid4())
        channel = "email"

        # Obtener client_id
        client_id = get_client_id_from_email(from_email)
        logging.info(f"✅ client_id asignado: {client_id}")

        # Límite de uso
        check_and_increment_usage(client_id, usage_type="messages_used")

        # Contar historial de sesión
        history_res = (
            supabase.table("history")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .execute()
        )
        total_messages = len(history_res.data or [])
        logging.info(f"💬 Mensajes previos en sesión {session_id}: {total_messages}")

        # Obtener límite dinámico
        try:
            settings_res = (
                supabase.table("client_settings")
                .select("session_message_limit")
                .eq("client_id", client_id)
                .limit(1)
                .execute()
            )
            session_limit = settings_res.data[0].get("session_message_limit", 24) if settings_res.data else 24
        except Exception as e:
            logging.warning(f"⚠️ Error obteniendo session_message_limit: {e}")
            session_limit = 24

        # Verificar límite
        if total_messages >= session_limit * 2:
            user_lang = detect_language(message)
            limit_messages = {
                "en": "You have reached the limit of this conversation. Please contact us by email or WhatsApp. 💬",
                "es": "Has alcanzado el límite de esta conversación. Contáctanos por correo o WhatsApp. 💬"
            }
            msg = limit_messages.get(user_lang, limit_messages["en"])
            save_history(client_id, session_id, "assistant", msg, channel)
            return {"answer": msg, "session_id": session_id, "limit_reached": True}

        # Historial reciente
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

        # Añadir mensaje actual
        history_messages.append({"role": "user", "content": message})

        # 🔥 Ejecutar pipeline RAG
        logging.info(f"📜 Contenido: {message}")
        answer = ask_question(history_messages, client_id, session_id=session_id)
        logging.info(f"✅ Respuesta generada correctamente desde el RAG.")

        # 💾 Guardar historial
        save_history(client_id, session_id, "user", message, channel)
        save_history(client_id, session_id, "assistant", answer, channel)

        # Responder
        return {
            "answer": answer,
            "session_id": session_id,
            "channel": channel
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception("❌ Error inesperado en /chat_email")
        raise HTTPException(status_code=500, detail="Error processing email message.")
