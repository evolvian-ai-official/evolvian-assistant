import httpx
import os
import logging
from typing import List, Optional

from api.modules.assistant_rag.supabase_client import supabase

logger = logging.getLogger(__name__)

MAX_WHATSAPP_LENGTH = 4096


# =====================================================
# 1️⃣ TEXTO LIBRE — CHAT RAG / WIDGET / CONVERSACIÓN ACTIVA
# =====================================================
async def send_whatsapp_message(
    to_number: str,
    text: str,
    channel: dict | None = None
) -> bool:
    """
    ✅ USAR PARA:
    - Chat RAG WhatsApp
    - Widget
    - Conversaciones activas

    ❌ NO usa Meta Templates
    """

    wa_phone_id = None
    wa_token = None

    # Normalizar channel
    if channel:
        if isinstance(channel, list):
            channel = channel[0]
        if isinstance(channel, dict) and "data" in channel:
            channel = channel["data"][0]

        wa_phone_id = channel.get("wa_phone_id")
        wa_token = channel.get("wa_token")

    # Fallback ENV (legacy / local)
    if not wa_phone_id:
        wa_phone_id = os.getenv("WHATSAPP_PHONE_ID")

    if not wa_token:
        wa_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not wa_phone_id or not wa_token:
        logger.error("❌ WhatsApp credentials not configured")
        return False

    meta_url = f"https://graph.facebook.com/v22.0/{wa_phone_id}/messages"

    # Truncate safety
    if len(text) > MAX_WHATSAPP_LENGTH:
        text = text[:MAX_WHATSAPP_LENGTH - 20] + "\n\n(…mensaje truncado)"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    }

    headers = {
        "Authorization": f"Bearer {wa_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(meta_url, json=payload, headers=headers)

        if res.status_code >= 400:
            logger.error("❌ WhatsApp TEXT failed | %s", res.text)
            return False

        logger.info("✅ WhatsApp TEXT sent | to=%s", to_number)
        return True

    except Exception:
        logger.exception("❌ WhatsApp TEXT error")
        return False


# =====================================================
# 2️⃣ WRAPPER CLIENTE — TEXTO (CHAT RAG)
# =====================================================
async def send_whatsapp_message_for_client(
    client_id: str,
    to_number: str,
    message: str,
) -> bool:
    """
    ✅ USAR PARA:
    - Chat RAG
    - Widget
    """

    resp = (
        supabase
        .table("channels")
        .select("wa_phone_id, wa_token")
        .eq("client_id", client_id)
        .eq("type", "whatsapp")
        .eq("is_active", True)
        .single()
        .execute()
    )

    if not resp.data:
        logger.error("❌ WhatsApp no configurado | client_id=%s", client_id)
        return False

    to_number = to_number.replace(" ", "")

    return await send_whatsapp_message(
        to_number=to_number,
        text=message,
        channel=resp.data
    )

# =====================================================
# 3️⃣ META TEMPLATE — SENDER REAL (REMINDERS / OUTBOUND)
# =====================================================
async def send_meta_template(
    *,
    to_number: str,
    template_name: str,
    language_code: str,
    parameters: List[str],
    phone_number_id: str,
    access_token: str,
) -> bool:
    """
    ✅ USAR SOLO PARA:
    - Reminders
    - Cron jobs
    - Outbound iniciado por la empresa

    ⚠️ SOLO templates POSICIONALES {{1}}, {{2}}
    """

    # -------------------------------------------------
    # Normalizar número (Meta Templates NO acepta '+')
    # -------------------------------------------------
    to_number = to_number.replace("+", "").replace(" ", "").strip()

    # -------------------------------------------------
    # Validaciones duras (anti Meta #100)
    # -------------------------------------------------
    if not parameters or not isinstance(parameters, list):
        logger.error("❌ Template parameters invalid | template=%s", template_name)
        return False

    if any(p is None or str(p).strip() == "" for p in parameters):
        logger.error(
            "❌ Template parameters empty | template=%s | params=%s",
            template_name,
            parameters,
        )
        return False

    meta_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

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
        "📤 META TEMPLATE sending",
        extra={
            "to": to_number,
            "template": template_name,
            "language": language_code,
            "params": parameters,
        },
    )

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(meta_url, json=payload, headers=headers)

    if res.status_code >= 400:
        logger.error(
            "❌ META TEMPLATE failed",
            extra={
                "status": res.status_code,
                "response": res.text,
                "template": template_name,
            },
        )
        return False

    logger.info("✅ META TEMPLATE sent | template=%s", template_name)
    return True

# =====================================================
# 4️⃣ WRAPPER CLIENTE — META TEMPLATE (REMINDERS)
# =====================================================
async def send_whatsapp_template_for_client(
    *,
    client_id: str,
    to_number: str,
    template_name: str,
    parameters: List[str],
    language_code: str = "es_MX",
) -> bool:
    """
    ✅ USAR SOLO PARA:
    - Reminders
    - Outbound
    ❌ NO usar para chat RAG
    """

    resp = (
        supabase
        .table("channels")
        .select("wa_phone_id, wa_token")
        .eq("client_id", client_id)
        .eq("type", "whatsapp")
        .eq("is_active", True)
        .single()
        .execute()
    )

    if not resp.data:
        logger.error("❌ WhatsApp no configurado | client_id=%s", client_id)
        return False

    to_number = to_number.replace("+", "").replace(" ", "").strip()

    return await send_meta_template(
        to_number=to_number,
        template_name=template_name,
        language_code=language_code,
        parameters=parameters,
        phone_number_id=resp.data["wa_phone_id"],
        access_token=resp.data["wa_token"],
    )
