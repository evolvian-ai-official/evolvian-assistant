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
    ⚠️ NO usar para chat libre / RAG.
    """

    phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_ID")
    access_token = access_token or os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        raise RuntimeError("Meta WhatsApp credentials not configured")

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": p} for p in parameters
                    ]
                }
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    logger.info("📤 Sending Meta template", extra={
        "to": to_number,
        "template": template_name,
        "language": language_code,
        "params": parameters,
    })

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(url, json=payload, headers=headers)

    if res.status_code >= 400:
        logger.error(
            "❌ Meta template send failed | status=%s | response=%s",
            res.status_code,
            res.text,
        )
        raise RuntimeError("Meta template send failed")

    return True
