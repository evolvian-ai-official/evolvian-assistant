# api/twilio_webhook.py

from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from api.modules.assistant_rag.rag_pipeline import ask_question
from api.modules.assistant_rag.supabase_client import get_client_id_by_channel, save_history

app = FastAPI()

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...)
):
    print(f"📩 Mensaje recibido de {From}: {Body}")

    # Buscar client_id desde Supabase
    client_id = get_client_id_by_channel("whatsapp", From)

    if not client_id:
        print("❌ Número no registrado en tabla channels.")
        return PlainTextResponse("Número no registrado.", status_code=200)

    try:
        respuesta = ask_question(Body, client_id)
        print(f"🤖 Respuesta generada: {respuesta}")

        # Guardar en historial con canal = whatsapp
        save_history(client_id, Body, respuesta, channel="whatsapp")

    except Exception as e:
        respuesta = "Lo siento, hubo un error procesando tu pregunta."
        print("❌ Error:", e)

    twiml_response = MessagingResponse()
    twiml_response.message(respuesta)
    return PlainTextResponse(str(twiml_response), status_code=200)
