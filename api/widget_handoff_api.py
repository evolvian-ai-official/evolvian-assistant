from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.modules.assistant_rag.supabase_client import supabase
from api.security.request_limiter import enforce_rate_limit, get_request_ip
from api.utils.feature_access import require_client_feature


router = APIRouter()
logger = logging.getLogger(__name__)


class WidgetHandoffRequestInput(BaseModel):
    public_client_id: str
    session_id: str
    channel: str = "widget"
    trigger: Optional[str] = "manual_request"
    reason: Optional[str] = "user_requested_human"
    confidence_score: Optional[float] = None
    user_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    accepted_terms: bool = False
    accepted_email_marketing: bool = False
    consent_token: Optional[str] = None
    last_user_message: Optional[str] = None
    last_ai_message: Optional[str] = None
    language: Optional[str] = "es"


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _localized_confirmation(lang: str) -> dict:
    language = "en" if str(lang or "").lower().startswith("en") else "es"
    if language == "en":
        return {
            "confirmation_message": "We received your request. A human agent will review it and reply as soon as possible.",
            "fallback_message": "We are checking your question and will respond as soon as possible.",
        }
    return {
        "confirmation_message": "Recibimos tu solicitud. Un agente humano la revisará y responderá lo antes posible.",
        "fallback_message": "Estamos revisando tu consulta y te responderemos lo antes posible.",
    }


@router.post("/widget/handoff/request")
async def create_widget_handoff_request(data: WidgetHandoffRequestInput, request: Request):
    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="widget_handoff_request_ip",
            key=f"{data.public_client_id}:{request_ip}",
            limit=20,
            window_seconds=60,
        )

        client_res = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", data.public_client_id)
            .limit(1)
            .execute()
        )
        if not client_res or not client_res.data:
            raise HTTPException(status_code=404, detail="Client not found")

        client_id = client_res.data[0]["id"]
        require_client_feature(client_id, "handoff", required_plan_label="premium")
        user_name = (data.user_name or "").strip()
        email_value = _normalize_email(data.email)
        phone_value = _normalize_phone(data.phone)

        if not user_name:
            raise HTTPException(status_code=422, detail="user_name is required")
        if not email_value and not phone_value:
            raise HTTPException(status_code=422, detail="email or phone is required")
        if not bool(data.accepted_terms):
            raise HTTPException(status_code=422, detail="accepted_terms is required for human follow-up")

        consent_token = (data.consent_token or "").strip() or None
        if not consent_token:
            consent_payload = {
                "client_id": client_id,
                "email": email_value,
                "phone": phone_value,
                "accepted_terms": True,
                "accepted_email_marketing": bool(data.accepted_email_marketing),
                "consent_at": datetime.utcnow().isoformat(),
                "ip_address": request_ip,
                "user_agent": request.headers.get("user-agent"),
            }
            consent_res = supabase.table("widget_consents").insert(consent_payload).execute()
            if consent_res and isinstance(consent_res.data, list) and consent_res.data:
                consent_token = consent_res.data[0].get("id")

        conversation_id = None
        try:
            convo_res = (
                supabase.table("conversations")
                .select("id")
                .eq("client_id", client_id)
                .eq("session_id", data.session_id)
                .maybe_single()
                .execute()
            )
            if convo_res and convo_res.data:
                conversation_id = convo_res.data.get("id")
                supabase.table("conversations").update(
                    {
                        "status": "needs_human",
                        "primary_channel": (data.channel or "widget").strip().lower(),
                        "contact_name": user_name,
                        "contact_email": email_value,
                        "contact_phone": phone_value,
                        "latest_message_at": datetime.utcnow().isoformat(),
                        "last_message_preview": (data.last_user_message or data.last_ai_message or "")[:240] or None,
                    }
                ).eq("id", conversation_id).execute()
            else:
                convo_insert = (
                    supabase.table("conversations")
                    .insert(
                        {
                            "client_id": client_id,
                            "session_id": data.session_id,
                            "status": "needs_human",
                            "primary_channel": (data.channel or "widget").strip().lower(),
                            "contact_name": user_name,
                            "contact_email": email_value,
                            "contact_phone": phone_value,
                            "latest_message_at": datetime.utcnow().isoformat(),
                            "last_message_preview": (data.last_user_message or data.last_ai_message or "")[:240] or None,
                        }
                    )
                    .execute()
                )
                if convo_insert and isinstance(convo_insert.data, list) and convo_insert.data:
                    conversation_id = convo_insert.data[0].get("id")
        except Exception as convo_error:
            logger.warning("Widget handoff: conversations table unavailable or insert failed: %s", convo_error)

        handoff_payload = {
            "client_id": client_id,
            "conversation_id": conversation_id,
            "session_id": data.session_id,
            "channel": (data.channel or "widget").strip().lower(),
            "trigger": (data.trigger or "manual_request").strip().lower(),
            "reason": (data.reason or "user_requested_human").strip().lower(),
            "status": "open",
            "confidence_score": data.confidence_score,
            "contact_name": user_name,
            "contact_email": email_value,
            "contact_phone": phone_value,
            "accepted_terms": True,
            "accepted_email_marketing": bool(data.accepted_email_marketing),
            "consent_token": consent_token,
            "last_user_message": (data.last_user_message or "").strip() or None,
            "last_ai_message": (data.last_ai_message or "").strip() or None,
            "ip_address": request_ip,
            "user_agent": request.headers.get("user-agent"),
            "metadata": {
                "public_client_id": data.public_client_id,
                "language": "en" if str(data.language or "").lower().startswith("en") else "es",
            },
        }
        handoff_res = supabase.table("conversation_handoff_requests").insert(handoff_payload).execute()
        if not handoff_res or not handoff_res.data:
            raise HTTPException(status_code=500, detail="Failed to create handoff request")

        handoff_id = handoff_res.data[0].get("id") if isinstance(handoff_res.data, list) else None

        alert_created = False
        try:
            alert_res = (
                supabase.table("conversation_alerts")
                .insert(
                    {
                        "client_id": client_id,
                        "conversation_id": conversation_id,
                        "source_handoff_request_id": handoff_id,
                        "alert_type": "human_intervention",
                        "status": "open",
                        "priority": "normal",
                        "title": "Human intervention requested",
                        "body": (data.last_user_message or data.last_ai_message or "Widget escalation request")[:500],
                    }
                )
                .execute()
            )
            alert_created = bool(alert_res and getattr(alert_res, "data", None))
        except Exception as alert_error:
            logger.warning("Widget handoff: conversation_alerts insert failed: %s", alert_error)

        localized = _localized_confirmation(data.language or "es")
        return {
            "success": True,
            "client_id": client_id,
            "conversation_id": conversation_id,
            "handoff_request_id": handoff_id,
            "consent_token": consent_token,
            "alert_created": alert_created,
            **localized,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating widget handoff request")
        raise HTTPException(status_code=500, detail="Failed to create handoff request")
