from fastapi import APIRouter, Request, BackgroundTasks, HTTPException

from api.modules.assistant_rag.rag_pipeline import handle_message
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message
from api.modules.assistant_rag.supabase_client import (
    get_channel_by_wa_phone_id,
    is_duplicate_wa_message,
    register_wa_message,
)

router = APIRouter(prefix="/api/whatsapp")

VERIFY_TOKEN = "evolvian2025"

# -------------------------------------------------------------------
# 🔐 Webhook verification (Meta GET)
# -------------------------------------------------------------------
@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ WhatsApp Webhook Verified")
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# -------------------------------------------------------------------
# 📩 Incoming WhatsApp messages (Meta POST)
# -------------------------------------------------------------------
@router.post("/webhook")
async def incoming_message(
    request: Request,
    background_tasks: BackgroundTasks
):
    print("🚀🚀🚀 WHATSAPP WEBHOOK HIT 🚀🚀🚀")

    try:
        payload = await request.json()

        # 🔴 CRÍTICO
        # Respondemos 200 INMEDIATO a Meta para evitar retries
        background_tasks.add_task(process_whatsapp_payload, payload)

        return {"received": True}

    except Exception as e:
        # ⚠️ JAMÁS devolver 4xx/5xx a Meta por errores internos
        # o entrará en retry infinito
        print("❌ WhatsApp webhook parse error:", str(e))
        return {"received": True}


# -------------------------------------------------------------------
# 🧠 Background processor (NO bloquea webhook)
# -------------------------------------------------------------------
async def process_whatsapp_payload(payload: dict):
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})

        # -------------------------------------------------------------
        # 🛑 Ignorar callbacks de estado (sent, delivered, read)
        # -------------------------------------------------------------
        if "statuses" in value:
            print("ℹ️ Status callback ignored")
            return

        messages = value.get("messages")
        if not messages:
            return

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        if not phone_number_id:
            return

        # -------------------------------------------------------------
        # Procesar TODOS los mensajes (Meta puede mandar batch)
        # -------------------------------------------------------------
        for message in messages:
            if message.get("type") != "text":
                continue

            wa_message_id = message.get("id")
            from_number = message.get("from")
            user_text = message.get("text", {}).get("body")

            if not wa_message_id or not from_number or not user_text:
                continue

            print("📩 Incoming WA message:", wa_message_id, user_text)

            # ---------------------------------------------------------
            # Resolver canal / cliente (MULTITENANT)
            # ---------------------------------------------------------
            channel = get_channel_by_wa_phone_id(phone_number_id)
            if not channel:
                print("⚠️ Unknown channel")
                continue

            client_id = channel.get("client_id")
            if not client_id:
                print("⚠️ Channel without client_id")
                continue

            # ---------------------------------------------------------
            # 🛑 DEDUPE CRÍTICO (idempotency por wamid)
            # ---------------------------------------------------------
            if is_duplicate_wa_message(wa_message_id):
                print("🔁 Duplicate message ignored:", wa_message_id)
                continue

            # Registrar inmediatamente para bloquear retries
            register_wa_message(
                wa_message_id=wa_message_id,
                client_id=client_id,
                from_number=from_number,
            )

            session_id = f"whatsapp-{from_number}"

            # ---------------------------------------------------------
            # Ejecutar RAG
            # ---------------------------------------------------------
            assistant_response = await handle_message(
                client_id=client_id,
                session_id=session_id,
                user_message=user_text,
                channel="whatsapp",
            )

            # ---------------------------------------------------------
            # Enviar respuesta SOLO una vez
            # ---------------------------------------------------------
            await send_whatsapp_message(
                to_number=from_number,
                text=assistant_response,
                channel=channel,
            )

            print("✅ WhatsApp message processed:", wa_message_id)

    except Exception as e:
        # ⚠️ Nunca levantar excepción aquí
        # Meta YA recibió 200 OK
        print("❌ WhatsApp background error:", str(e))
