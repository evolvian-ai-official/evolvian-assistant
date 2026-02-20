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

VERIFY_TOKEN = (os.getenv("META_WHATSAPP_VERIFY_TOKEN") or "").strip()
if not VERIFY_TOKEN:
    logger.error("META_WHATSAPP_VERIFY_TOKEN is not configured.")


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
    if not VERIFY_TOKEN:
        return PlainTextResponse(content="Webhook verify token is not configured", status_code=503)

    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    return PlainTextResponse(content="Verification token mismatch", status_code=403)


@router.post("/webhooks/meta")
async def receive_whatsapp_message(request: Request):
    try:
        raw_body = await request.body()
        verify_meta_signature(request, raw_body)
        data = json.loads(raw_body.decode("utf-8") or "{}")

        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return JSONResponse(content={"status": "no_message"}, status_code=200)

        msg = messages[0]
        user_phone = msg.get("from")
        text = _extract_message_text(msg)

        if not user_phone or not text:
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        business_phone = value.get("metadata", {}).get("display_phone_number")
        if not business_phone:
            return JSONResponse(status_code=400, content={"error": "Número del negocio no encontrado"})
        formatted_value = f"whatsapp:+{business_phone.lstrip('+')}"

        try:
            client_id = get_client_id_by_channel("whatsapp", formatted_value)
            if not client_id or not isinstance(client_id, str) or len(client_id) < 30:
                raise ValueError("client_id inválido o ausente")
        except Exception:
            return JSONResponse(status_code=404, content={"error": "Cliente no encontrado"})

        credentials = get_whatsapp_credentials(client_id)

        message_type = msg.get("type") or ""
        if _is_cancel_action(message_type, msg, text):
            try:
                _, response = await _cancel_appointment_from_whatsapp(client_id, user_phone)
            except Exception:
                logger.exception("❌ Error cancelando cita desde webhook legacy")
                response = "⚠️ No pude cancelar tu cita en este momento. Intenta de nuevo."
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

        # 🔧 Ajuste temporal para evitar error (#131030) con +521
        if user_phone.startswith("521"):
            user_phone = "52" + user_phone[3:]

        if response:
            send_whatsapp_message(
                to_number=f"+{user_phone}",
                message=response,
                token=credentials["wa_token"],
                phone_id=credentials["wa_phone_id"]
            )

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error procesando webhook Meta")
        return JSONResponse(status_code=500, content={"error": "internal_server_error"})
