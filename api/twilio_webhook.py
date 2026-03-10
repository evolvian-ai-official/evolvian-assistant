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


def _normalize_wa_number(raw_value: str | None) -> str:
    raw = str(raw_value or "").strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()
    return raw


def _build_channel_candidates(raw_value: str | None) -> list[str]:
    normalized = _normalize_wa_number(raw_value)
    if not normalized:
        return []
    with_plus = normalized if normalized.startswith("+") else f"+{normalized}"
    without_plus = with_plus.lstrip("+")
    candidates = [f"whatsapp:{with_plus}"]
    if without_plus and without_plus != with_plus:
        candidates.append(f"whatsapp:{without_plus}")
    return candidates


def _resolve_client_id_for_twilio(to_value: str | None, from_value: str | None) -> str | None:
    # Prefer "To" (business number) because channel mapping is tenant-owned.
    for candidate in _build_channel_candidates(to_value):
        client_id = get_client_id_by_channel("whatsapp", candidate)
        if client_id:
            return client_id

    # Backward-compatible fallback: old behavior by user "From".
    for candidate in _build_channel_candidates(from_value):
        client_id = get_client_id_by_channel("whatsapp", candidate)
        if client_id:
            return client_id
    return None


@router.post("/twilio-webhook")
async def twilio_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    To: str | None = Form(default=None),
):
    form_data = await request.form()
    verify_twilio_signature(request, form_data)

    print(f"📩 Mensaje recibido de {From} hacia {To}: {Body}")

    # Número del usuario para sesión
    numero = _normalize_wa_number(From)

    # Buscar client_id asociado preferentemente al número de negocio (To).
    client_id = _resolve_client_id_for_twilio(To, From)
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
    except Exception as e:
        print(f"❌ Error al generar respuesta RAG: {e}")
        respuesta = "Lo siento, ocurrió un error procesando tu pregunta."

    # Preparar y devolver respuesta a Twilio
    twiml_response = MessagingResponse()
    if respuesta:
        twiml_response.message(respuesta)
    else:
        print("🤫 Respuesta suprimida por política de autorespuesta institucional.")

    return Response(content=str(twiml_response), media_type="application/xml")
