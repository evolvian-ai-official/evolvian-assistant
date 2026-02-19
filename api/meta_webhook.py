from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import os
import json
import logging
from api.modules.assistant_rag.supabase_client import (
    get_client_id_by_channel,
    get_whatsapp_credentials,
)
from api.modules.assistant_rag.intent_router import process_user_message
from api.modules.whatsapp.send_wa_message import send_whatsapp_message
from api.modules.whatsapp.webhook import _cancel_appointment_from_whatsapp, _is_cancel_action
from api.webhook_security import verify_meta_signature

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "evolviansecret2025")
if VERIFY_TOKEN == "evolviansecret2025":
    logger.warning("⚠️ Using default META_WHATSAPP_VERIFY_TOKEN. Configure env var in production.")


def _extract_message_text(msg: dict) -> str | None:
    message_type = msg.get("type")

    if message_type == "text":
        return msg.get("text", {}).get("body")

    if message_type == "interactive":
        interactive = msg.get("interactive") or {}
        button = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}
        return (
            button.get("title")
            or button.get("id")
            or list_reply.get("title")
            or list_reply.get("id")
        )

    if message_type == "button":
        button = msg.get("button") or {}
        return button.get("text") or button.get("payload")

    return None


@router.get("/webhooks/meta")
def verify_webhook(request: Request):
    print("🧪 Entró a verify_webhook")
    params = request.query_params
    print(f"📝 Parámetros recibidos en la verificación: {params}")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        print("✅ Webhook Meta verificado correctamente")
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    print("❌ Token inválido o modo incorrecto en la verificación")
    return PlainTextResponse(content="Verification token mismatch", status_code=403)


@router.post("/webhooks/meta")
async def receive_whatsapp_message(request: Request):
    try:
        raw_body = await request.body()
        verify_meta_signature(request, raw_body)
        data = json.loads(raw_body.decode("utf-8") or "{}")
        print("📥 Webhook recibido:", data)

        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            print("⚠️ No se encontró mensaje en el webhook")
            return JSONResponse(content={"status": "no_message"}, status_code=200)

        msg = messages[0]
        user_phone = msg.get("from")
        text = _extract_message_text(msg)

        if not user_phone or not text:
            print("⚠️ Mensaje sin texto procesable en webhook Meta")
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        print(f"📞 Mensaje de {user_phone}: {text}")

        business_phone = value.get("metadata", {}).get("display_phone_number")
        if not business_phone:
            print("❌ No se pudo extraer el número del negocio")
            return JSONResponse(status_code=400, content={"error": "Número del negocio no encontrado"})

        print(f"🔑 Número de negocio extraído: {business_phone}")
        formatted_value = f"whatsapp:+{business_phone.lstrip('+')}"
        print(f"🔍 Formateado el número de WhatsApp: {formatted_value}")

        try:
            client_id = get_client_id_by_channel("whatsapp", formatted_value)
            print(f"📦 client_id encontrado: {client_id}")
            if not client_id or not isinstance(client_id, str) or len(client_id) < 30:
                raise ValueError("client_id inválido o ausente")
        except Exception as e:
            print(f"❌ Error buscando client_id: {e}")
            return JSONResponse(status_code=404, content={"error": "Cliente no encontrado"})

        credentials = get_whatsapp_credentials(client_id)
        print(f"🔑 Credenciales de WhatsApp obtenidas: {credentials}")

        message_type = msg.get("type") or ""
        if _is_cancel_action(message_type, msg, text):
            try:
                _, response = _cancel_appointment_from_whatsapp(client_id, user_phone)
            except Exception:
                logger.exception("❌ Error cancelando cita desde webhook legacy")
                response = "⚠️ No pude cancelar tu cita en este momento. Intenta de nuevo."
            print(f"💬 Respuesta cancelación: {response}")
        else:
            # ✅ Procesar con intent router (agenda + RAG)
            session_id = f"whatsapp-{user_phone}"
            response = await process_user_message(
                client_id=client_id,
                session_id=session_id,
                message=text,
                channel="whatsapp",
                provider="meta",
            )
            print(f"💬 Respuesta generada por RAG: {response}")

        # 🔧 Ajuste temporal para evitar error (#131030) con +521
        if user_phone.startswith("521"):
            user_phone = "52" + user_phone[3:]
            print(f"📞 Ajustando número para Meta Sandbox: {user_phone}")

        send_whatsapp_message(
            to_number=f"+{user_phone}",
            message=response,
            token=credentials["wa_token"],
            phone_id=credentials["wa_phone_id"]
        )
        print(f"✅ Mensaje enviado a {user_phone} con éxito.")

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error procesando mensaje: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
