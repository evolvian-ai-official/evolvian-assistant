import httpx
import os
import logging
import re
from typing import List, Optional

from api.compliance.outbound_policy import (
    evaluate_outbound_policy,
    log_outbound_policy_event,
)
from api.modules.assistant_rag.supabase_client import supabase
from api.security.whatsapp_token_crypto import decrypt_whatsapp_token

logger = logging.getLogger(__name__)

MAX_WHATSAPP_LENGTH = 4096


def _sanitize_meta_template_param(value: str) -> str:
    """
    Meta template text params cannot include new lines/tabs
    or runs of >4 consecutive spaces.
    """
    text = str(value or "")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


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
        wa_token = decrypt_whatsapp_token(channel.get("wa_token"))

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
            logger.error("❌ WhatsApp TEXT failed | status=%s", res.status_code)
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
    *,
    purpose: str = "transactional",
    recipient_email: str | None = None,
    policy_source: str = "whatsapp_text",
    policy_source_id: str | None = None,
) -> bool:
    """
    ✅ USAR PARA:
    - Chat RAG
    - Widget
    """

    policy = evaluate_outbound_policy(
        client_id=client_id,
        channel="whatsapp",
        purpose=purpose,
        recipient_email=recipient_email,
        recipient_phone=to_number,
        source=policy_source,
        source_id=policy_source_id,
    )
    if not policy.get("allowed"):
        log_outbound_policy_event(
            client_id=client_id,
            policy_result=policy,
            stage="pre_send",
            send_status="blocked_policy",
            send_error=str(policy.get("reason") or "policy_blocked"),
        )
        logger.warning(
            "⛔ WhatsApp TEXT blocked by outbound policy | client_id=%s | reason=%s | proof_id=%s",
            client_id,
            policy.get("reason"),
            policy.get("proof_id"),
        )
        return False

    log_outbound_policy_event(
        client_id=client_id,
        policy_result=policy,
        stage="pre_send",
        send_status="allowed_policy",
    )

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

    channel = dict(resp.data[0] or {})  # ✅ FIX CLAVE
    channel["wa_token"] = decrypt_whatsapp_token(channel.get("wa_token"))

    to_number = to_number.replace(" ", "").strip()

    sent = await send_whatsapp_message(
        to_number=to_number,
        text=message,
        channel=channel,  # ✅ dict, no lista
    )
    log_outbound_policy_event(
        client_id=client_id,
        policy_result=policy,
        stage="post_send",
        send_status="sent" if sent else "failed",
        send_error=None if sent else "provider_send_failed",
    )
    return sent


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

    normalized_parameters = [_sanitize_meta_template_param(str(p or "")) for p in parameters]

    if any(p == "" for p in normalized_parameters):
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
                    {"type": "text", "text": p}
                    for p in normalized_parameters
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
                "❌ META TEMPLATE failed | template=%s | status=%s",
                template_name,
                status_code,
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
    purpose: str = "transactional",
    recipient_email: str | None = None,
    policy_source: str = "whatsapp_template",
    policy_source_id: str | None = None,
) -> dict:
    """
    Multi-tenant Meta Template sender.

    Returns structured response from send_meta_template.
    """

    try:
        policy = evaluate_outbound_policy(
            client_id=client_id,
            channel="whatsapp",
            purpose=purpose,
            recipient_email=recipient_email,
            recipient_phone=to_number,
            source=policy_source,
            source_id=policy_source_id,
        )
        if not policy.get("allowed"):
            log_outbound_policy_event(
                client_id=client_id,
                policy_result=policy,
                stage="pre_send",
                send_status="blocked_policy",
                send_error=str(policy.get("reason") or "policy_blocked"),
            )
            reason = str(policy.get("reason") or "policy_blocked")
            logger.warning(
                "⛔ Meta template blocked by outbound policy | client_id=%s | template=%s | reason=%s | proof_id=%s",
                client_id,
                template_name,
                reason,
                policy.get("proof_id"),
            )
            return {
                "success": False,
                "meta_message_id": None,
                "status_code": None,
                "error": f"policy_blocked:{reason}",
                "raw": None,
                "policy_proof_id": policy.get("proof_id"),
            }

        log_outbound_policy_event(
            client_id=client_id,
            policy_result=policy,
            stage="pre_send",
            send_status="allowed_policy",
        )

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
            log_outbound_policy_event(
                client_id=client_id,
                policy_result=policy,
                stage="post_send",
                send_status="failed",
                send_error="whatsapp_channel_not_configured",
            )
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
                "policy_proof_id": policy.get("proof_id"),
            }

        channel = dict(resp.data[0] or {})
        channel["wa_token"] = decrypt_whatsapp_token(channel.get("wa_token"))

        send_result = await send_meta_template(
            to_number=to_number,
            template_name=template_name,
            language_code=language_code,
            parameters=parameters,
            phone_number_id=channel["wa_phone_id"],
            access_token=channel["wa_token"],
        )
        log_outbound_policy_event(
            client_id=client_id,
            policy_result=policy,
            stage="post_send",
            send_status="sent" if send_result.get("success") else "failed",
            provider_message_id=send_result.get("meta_message_id"),
            send_error=None if send_result.get("success") else send_result.get("error"),
        )
        send_result["policy_proof_id"] = policy.get("proof_id")
        return send_result

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
            "policy_proof_id": None,
        }
