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
        .limit(1)
        .execute()
    )

    if not resp.data:
        logger.error("❌ WhatsApp no configurado | client_id=%s", client_id)
        return False

    channel = resp.data[0]  # ✅ FIX CLAVE

    to_number = to_number.replace(" ", "").strip()

    return await send_whatsapp_message(
        to_number=to_number,
        text=message,
        channel=channel,  # ✅ dict, no lista
    )


# =====================================================
# 3️⃣ META TEMPLATE — SENDER REAL (PRODUCTION READY)
# =====================================================
async def send_meta_template(
    *,
    to_number: str,
    template_name: str,
    language_code: str,
    parameters: Optional[List[str]] = None,
    phone_number_id: str,
    access_token: str,
) -> dict:
    """
    Production-ready Meta Template sender.

    Returns:
        {
            "success": bool,
            "meta_message_id": str | None,
            "status_code": int | None,
            "error": str | None,
            "raw": dict | None
        }
    """

    # -------------------------------
    # Normalize number
    # -------------------------------
    to_number = to_number.replace("+", "").replace(" ", "").strip()

    # -------------------------------
    # Hard validations
    # -------------------------------
    if parameters is None:
        parameters = []

    if not isinstance(parameters, list):
        return {
            "success": False,
            "meta_message_id": None,
            "status_code": None,
            "error": "Invalid parameters list",
            "raw": None,
        }

    if any(p is None or str(p).strip() == "" for p in parameters):
        return {
            "success": False,
            "meta_message_id": None,
            "status_code": None,
            "error": "Empty template parameter detected",
            "raw": None,
        }

    meta_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    template_payload = {
        "name": template_name,
        "language": {"code": language_code},
    }

    if parameters:
        template_payload["components"] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(p)}
                    for p in parameters
                ],
            }
        ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": template_payload,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(meta_url, json=payload, headers=headers)

        status_code = res.status_code

        if status_code >= 400:
            logger.error(
                "❌ META TEMPLATE failed | template=%s | status=%s | response=%s",
                template_name,
                status_code,
                res.text,
            )
            return {
                "success": False,
                "meta_message_id": None,
                "status_code": status_code,
                "error": res.text,
                "raw": None,
            }

        meta_response = res.json()

        meta_message_id = None
        if "messages" in meta_response:
            meta_message_id = meta_response["messages"][0].get("id")

        logger.info(
            "✅ META TEMPLATE sent | template=%s | message_id=%s",
            template_name,
            meta_message_id,
        )

        return {
            "success": True,
            "meta_message_id": meta_message_id,
            "status_code": status_code,
            "error": None,
            "raw": meta_response,
        }

    except Exception as e:
        logger.exception("❌ META TEMPLATE exception | template=%s", template_name)
        return {
            "success": False,
            "meta_message_id": None,
            "status_code": None,
            "error": str(e),
            "raw": None,
        }


# =====================================================
# 4️⃣ WRAPPER CLIENTE — META TEMPLATE (PRODUCTION READY)
# =====================================================
async def send_whatsapp_template_for_client(
    *,
    client_id: str,
    to_number: str,
    template_name: str,
    parameters: Optional[List[str]] = None,
    language_code: str = "es_MX",
) -> dict:
    """
    Multi-tenant Meta Template sender.

    Returns structured response from send_meta_template.
    """

    try:
        resp = (
            supabase
            .table("channels")
            .select("wa_phone_id, wa_token")
            .eq("client_id", client_id)
            .eq("type", "whatsapp")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if not resp.data:
            logger.error(
                "❌ WhatsApp not configured | client_id=%s",
                client_id,
            )
            return {
                "success": False,
                "meta_message_id": None,
                "status_code": None,
                "error": "WhatsApp channel not configured",
                "raw": None,
            }

        channel = resp.data[0]

        return await send_meta_template(
            to_number=to_number,
            template_name=template_name,
            language_code=language_code,
            parameters=parameters,
            phone_number_id=channel["wa_phone_id"],
            access_token=channel["wa_token"],
        )

    except Exception as e:
        logger.exception(
            "❌ Wrapper failure | client_id=%s | template=%s",
            client_id,
            template_name,
        )
        return {
            "success": False,
            "meta_message_id": None,
            "status_code": None,
            "error": str(e),
            "raw": None,
        }
