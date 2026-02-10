import httpx
import logging
import os

logger = logging.getLogger(__name__)


async def send_meta_template(
    *,
    to_number: str,
    template_name: str,
    language_code: str = "es_MX",
    parameters: list[str],
    phone_number_id: str | None = None,
    access_token: str | None = None,
):
    """
    Envía un mensaje WhatsApp usando TEMPLATE de Meta (POSICIONAL).

    ✔ SOLO templates con {{1}}, {{2}}, {{3}}
    ✔ SOLO BODY (sin header/footer)
    ✔ Producción estable (Meta Cloud API)
    """

    # -------------------------------------------------
    # 1️⃣ Credenciales
    # -------------------------------------------------
    phone_number_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID")
    access_token = access_token or os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.error("❌ Meta WhatsApp credentials missing")
        raise RuntimeError("Meta WhatsApp credentials not configured")

    # -------------------------------------------------
    # 2️⃣ Normalizar número (E.164 sin +)
    # -------------------------------------------------
    to_number = to_number.replace("+", "").strip()

    # -------------------------------------------------
    # 3️⃣ Validaciones duras (anti-bugs Meta)
    # -------------------------------------------------
    if not parameters or not isinstance(parameters, list):
        raise ValueError("Template parameters must be a non-empty list")

    if any(p is None or str(p).strip() == "" for p in parameters):
        raise ValueError("Template parameters cannot be empty")

    # -------------------------------------------------
    # 4️⃣ Endpoint
    # -------------------------------------------------
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    # -------------------------------------------------
    # 5️⃣ Payload CANÓNICO (PROBADO EN PROD)
    # -------------------------------------------------
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
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
        "📤 Sending Meta WhatsApp template",
        extra={
            "to": to_number,
            "template": template_name,
            "language": language_code,
            "parameters": parameters,
        },
    )

    # -------------------------------------------------
    # 6️⃣ Send
    # -------------------------------------------------
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json=payload, headers=headers)

    # -------------------------------------------------
    # 7️⃣ Errors explícitos
    # -------------------------------------------------
    if response.status_code >= 400:
        logger.error(
            "❌ Meta template send failed",
            extra={
                "status": response.status_code,
                "response": response.text,
                "payload": payload,
            },
        )
        raise RuntimeError(f"Meta template send failed: {response.text}")

    logger.info("✅ Meta template sent successfully")
    return response.json()
