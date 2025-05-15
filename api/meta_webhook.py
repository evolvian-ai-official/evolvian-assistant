from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import os
from api.modules.assistant_rag.supabase_client import (
    get_client_id_by_channel,
    get_whatsapp_credentials,
    save_history
)
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.modules.whatsapp.send_wa_message import send_whatsapp_message

router = APIRouter()

VERIFY_TOKEN = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "evolviansecret2025")

# ✅ Verificación del webhook de Meta
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

# ✅ Recepción y procesamiento de mensajes
@router.post("/webhooks/meta")
async def receive_whatsapp_message(request: Request):
    try:
        data = await request.json()
        print("📥 Webhook recibido:", data)

        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            print("⚠️ No se encontró mensaje en el webhook")
            return JSONResponse(content={"status": "no_message"}, status_code=200)

        msg = messages[0]
        user_phone = msg["from"]
        text = msg["text"]["body"]

        print(f"📞 Mensaje de {user_phone}: {text}")

        # 🟢 Usamos el número del negocio, no del usuario
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

        # ✅ Aquí está el orden corregido: pregunta primero, luego client_id
        response = ask_question(text, client_id)
        print(f"💬 Respuesta generada por RAG: {response}")

        send_whatsapp_message(
            to_number=user_phone,
            message=response,
            token=credentials["wa_token"],
            phone_id=credentials["wa_phone_id"]
        )
        print(f"✅ Mensaje enviado a {user_phone} con éxito.")

        save_history(client_id, text, response, channel="whatsapp")
        print(f"📂 Historial guardado para client_id {client_id}")

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        print(f"❌ Error procesando mensaje: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
