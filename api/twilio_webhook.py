# api/twilio_webhook.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from modules.assistant_rag.supabase_client import (
    get_client_id_by_channel,
    save_history,
    track_usage  # ✅ Importar la nueva función
)

from modules.assistant_rag.rag_pipeline import ask_question  # 👈 aquí se usa RAG

import config.config  # Asegura que las claves están cargadas desde .env

router = APIRouter()

@router.post("/twilio-webhook")
async def twilio_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...)
):
    print(f"📩 Mensaje recibido de {From}: {Body}")

    # Limpia número y busca en canal
    numero = From.replace("whatsapp:", "").strip()
    canal = f"whatsapp:{numero}"

    client_id = get_client_id_by_channel("whatsapp", canal)

    if not client_id:
        print("❌ Número no registrado en tabla channels.")
        twiml_response = MessagingResponse()
        twiml_response.message("Tu número no está asociado a ningún cliente. Por favor configura tu cuenta desde el panel.")
        return Response(content=str(twiml_response), media_type="application/xml")

    pregunta = Body

    try:
        respuesta = ask_question(pregunta, client_id)
        print(f"🤖 Respuesta generada: {respuesta}")
    except Exception as e:
        print(f"❌ Error al generar respuesta RAG: {e}")
        respuesta = "Lo siento, ocurrió un error procesando tu pregunta."

    # Guardar historial y registrar uso
    save_history(client_id, pregunta, respuesta, channel="whatsapp")  # ✅ canal agregado
    track_usage(client_id, channel="whatsapp", type="question")       # ✅ registrar uso

    twiml_response = MessagingResponse()
    twiml_response.message(respuesta)
    return Response(content=str(twiml_response), media_type="application/xml")
