# api/twilio_webhook.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from api.modules.assistant_rag.supabase_client import (
    get_client_id_by_channel,
)

from api.modules.assistant_rag.intent_router import process_user_message
from api.webhook_security import verify_twilio_signature


router = APIRouter()

@router.post("/twilio-webhook")
async def twilio_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...)
):
    form_data = await request.form()
    verify_twilio_signature(request, form_data)

    print(f"📩 Mensaje recibido de {From}: {Body}")

    # Limpiar y preparar número
    numero = From.replace("whatsapp:", "").strip()
    canal = f"whatsapp:{numero}"
    print(f"🔎 Canal buscado en Supabase: {canal}")

    # Buscar client_id asociado al número
    client_id = get_client_id_by_channel("whatsapp", canal)
    print(f"🧠 client_id encontrado: {client_id}")

    if not client_id:
        print("❌ Número no registrado en tabla channels.")
        twiml_response = MessagingResponse()
        twiml_response.message(
            "Tu número no está asociado a ningún cliente. Por favor configura tu cuenta desde el panel."
        )
        return Response(content=str(twiml_response), media_type="application/xml")

    pregunta = Body.strip()

    # Procesar pregunta con intent router (agenda + RAG)
    try:
        session_id = f"whatsapp-{numero}"
        respuesta = await process_user_message(
            client_id=client_id,
            session_id=session_id,
            message=pregunta,
            channel="whatsapp",
            provider="twilio",
        )
        print(f"🤖 Respuesta generada: {respuesta}")
        if not respuesta:
            respuesta = "No encontré información relacionada en tus documentos. Puedes cargar más desde tu panel."
    except Exception as e:
        print(f"❌ Error al generar respuesta RAG: {e}")
        respuesta = "Lo siento, ocurrió un error procesando tu pregunta."

    # Preparar y devolver respuesta a Twilio
    twiml_response = MessagingResponse()
    twiml_response.message(respuesta)

    return Response(content=str(twiml_response), media_type="application/xml")
