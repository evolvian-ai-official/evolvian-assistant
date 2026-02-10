import httpx
import logging
import os

logger = logging.getLogger(__name__)


async def send_meta_template(
    *,
    to_number: str,
    template_name: str,
    language_code: str,
    parameters: list[str],
    phone_number_id: str | None = None,
    access_token: str | None = None,
):
    """
    Envía un mensaje WhatsApp usando TEMPLATE de Meta.

    ✔ Diseñado para REMINDERS / OUTBOUND
    ❌ NO usar para chat libre / RAG
    ✔ Soporta multitenant (BYO WhatsApp Business)
    """

    # -------------------------------------------------
    # 1️⃣ Resolver credenciales (PRIORIDAD: cliente)
    # -------------------------------------------------
    phone_number_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID")
    access_token = access_token or os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.error("❌ Meta WhatsApp credentials missing")
        raise RuntimeError("Meta WhatsApp credentials not configured")

    # -------------------------------------------------
    # 2️⃣ Endpoint Meta
    # -------------------------------------------------
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    # -------------------------------------------------
    # 3️⃣ Payload TEMPLATE (orden importa)
    # -------------------------------------------------
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code,
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(p)}
                        for p in parameters
                    ],
                }
            ],
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    logger.info(
        "📤 Sending Meta template",
        extra={
            "to": to_number,
            "template": template_name,
            "language": language_code,
            "phone_number_id": phone_number_id,
        },
    )

    # -------------------------------------------------
    # 4️⃣ Send request
    # -------------------------------------------------
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json=payload, headers=headers)

    # -------------------------------------------------
    # 5️⃣ Error handling (CLARO)
    # -------------------------------------------------
    if response.status_code >= 400:
        logger.error(
            "❌ Meta template send failed",
            extra={
                "status": response.status_code,
                "response": response.text,
                "to": to_number,
                "template": template_name,
                "phone_number_id": phone_number_id,
            },
        )
        raise RuntimeError(
            f"Meta template send failed: {response.status_code}"
        )

    logger.info(
        "✅ Meta template sent successfully",
        extra={
            "to": to_number,
            "template": template_name,
        },
    )

    return True
