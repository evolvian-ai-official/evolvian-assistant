import httpx
import os
import logging

MAX_WHATSAPP_LENGTH = 4096


async def send_whatsapp_message(
    to_number: str,
    text: str,
    channel: dict | None = None
) -> bool:
    """
    Envía mensaje WhatsApp usando:
    1) Credenciales del channel (multitenant)
    2) Fallback a ENV (single-tenant legacy)
    """

    wa_phone_id = None
    wa_token = None

    # 🧠 NORMALIZAR channel (clave para Supabase)
    if channel:
        if isinstance(channel, list):
            channel = channel[0]
        if isinstance(channel, dict) and "data" in channel:
            channel = channel["data"][0]

        wa_phone_id = channel.get("wa_phone_id")
        wa_token = channel.get("wa_token")  # ✅ KEY CORRECTO

    # 🧯 FALLBACK: ENV (local / legacy)
    if not wa_phone_id:
        wa_phone_id = os.getenv("WHATSAPP_PHONE_ID")

    if not wa_token:
        wa_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not wa_phone_id or not wa_token:
        logging.error(
            "❌ WhatsApp credentials not configured | phone_id=%s | token=%s",
            wa_phone_id,
            "SET" if wa_token else "MISSING",
        )
        return False

    meta_url = f"https://graph.facebook.com/v22.0/{wa_phone_id}/messages"

    # ✂️ Truncate message safely
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
            response = await client.post(meta_url, json=payload, headers=headers)

            if response.status_code >= 400:
                logging.error(
                    "❌ WhatsApp send failed | status=%s | response=%s",
                    response.status_code,
                    response.text,
                )
                return False

            logging.info(
                "✅ WhatsApp message sent | to=%s | chars=%s",
                to_number,
                len(text),
            )
            return True

    except httpx.TimeoutException:
        logging.error("⏱ WhatsApp send timeout")
        return False

    except Exception:
        logging.exception("❌ Unexpected WhatsApp send error")
        return False

# =====================================================
# WRAPPER POR CLIENTE (REMINDERS / OUTBOUND)
# =====================================================

from api.modules.assistant_rag.supabase_client import supabase


async def send_whatsapp_message_for_client(
    client_id: str,
    to_number: str,
    message: str,
) -> bool:
    """
    Wrapper seguro para reminders / outbound WhatsApp.
    Debe ser async para no romper el event loop (FastAPI / workers).
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
        logging.error(
            "❌ WhatsApp no configurado para client_id=%s",
            client_id
        )
        return False

    # Normalización mínima del teléfono (Meta picky)
    to_number = to_number.replace(" ", "")

    # 🔥 Reutiliza la función base correctamente
    return await send_whatsapp_message(
        to_number=to_number,
        text=message,
        channel=resp.data
    )
