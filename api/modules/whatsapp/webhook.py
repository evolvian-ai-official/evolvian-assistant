from fastapi import APIRouter, Request, HTTPException

from api.modules.assistant_rag.rag_pipeline import handle_message
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message
from api.modules.assistant_rag.supabase_client import get_channel_by_wa_phone_id

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
async def incoming_message(request: Request):
    print("🚀🚀🚀 WHATSAPP WEBHOOK HIT 🚀🚀🚀")

    payload = await request.json()
    print("📦 RAW PAYLOAD:", payload)

    try:
        # -------------------------------------------------------------
        # 1️⃣ Parseo defensivo del payload
        # -------------------------------------------------------------
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})

        # -------------------------------------------------------------
        # 🛑 IGNORAR STATUS CALLBACKS (sent, delivered, read)
        # -------------------------------------------------------------
        if "statuses" in value:
            print("ℹ️ Status callback ignored")
            return {"ignored": "status"}

        # -------------------------------------------------------------
        # SOLO mensajes reales del usuario
        # -------------------------------------------------------------
        if "messages" not in value:
            return {"ignored": True}

        message = value["messages"][0]
        if message.get("type") != "text":
            return {"ignored": "non-text"}

        from_number = message["from"]
        user_text = message["text"]["body"]

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        if not phone_number_id:
            return {"error": "missing_phone_number_id"}

        print("📩 Message:", user_text)

        # -------------------------------------------------------------
        # 2️⃣ Resolver canal / cliente (MULTITENANT)
        # -------------------------------------------------------------
        channel = get_channel_by_wa_phone_id(phone_number_id)
        if not channel:
            return {"ignored": "unknown_channel"}

        client_id = channel.get("client_id")
        if not client_id:
            return {"error": "channel_without_client"}

        session_id = f"whatsapp-{from_number}"

        # -------------------------------------------------------------
        # 3️⃣ Ejecutar RAG
        # (handle_message es el ÚNICO que guarda historial)
        # -------------------------------------------------------------
        assistant_response = await handle_message(
            client_id=client_id,
            session_id=session_id,
            user_message=user_text,
            channel="whatsapp",
        )

        # -------------------------------------------------------------
        # 4️⃣ Enviar respuesta a WhatsApp
        # -------------------------------------------------------------
        await send_whatsapp_message(
            to_number=from_number,
            text=assistant_response,
            channel=channel,
        )

        print("✅ WhatsApp flow completed")
        return {"received": True}

    except Exception as e:
        print("❌ WhatsApp webhook error:", str(e))
        raise HTTPException(status_code=400, detail="Invalid WhatsApp payload")
