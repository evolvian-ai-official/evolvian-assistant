from datetime import datetime, timezone
import html
import json
import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.authz import authorize_client_request
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import send_reply as gmail_send_reply
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_message_for_client,
    send_whatsapp_template_for_client,
)
from api.utils.feature_access import require_client_feature


router = APIRouter()
logger = logging.getLogger(__name__)


class ConversationSendReplyInput(BaseModel):
    client_id: str
    message: str
    reply_channel: Optional[str] = None
    subject: Optional[str] = None
    thread_id: Optional[str] = None
    whatsapp_use_template: Optional[bool] = None
    whatsapp_template_name: Optional[str] = None
    whatsapp_template_language_code: Optional[str] = None
    mark_resolved: bool = False


def _norm_channel(value: Optional[str]) -> str:
    ch = str(value or "").strip().lower()
    if ch == "gmail":
        return "email"
    if ch == "chat":
        return "widget"
    return ch


def _json_response_payload(resp: JSONResponse) -> dict:
    try:
        body = getattr(resp, "body", b"") or b""
        if isinstance(body, bytes):
            return json.loads(body.decode("utf-8")) if body else {}
        if isinstance(body, str):
            return json.loads(body) if body else {}
    except Exception:
        return {}
    return {}


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _looks_like_uuid(value: str | None) -> bool:
    return bool(value and _UUID_RE.match(str(value).strip()))


def _default_whatsapp_template_language(handoff: dict) -> str:
    metadata = handoff.get("metadata") if isinstance(handoff.get("metadata"), dict) else {}
    lang = str((metadata or {}).get("language") or "").strip().lower()
    return "en_US" if lang.startswith("en") else "es_MX"


def _derive_email_thread_id(client_id: str, session_id: str | None, explicit_thread_id: str | None) -> Optional[str]:
    thread_id = str(explicit_thread_id or "").strip()
    if thread_id:
        return thread_id
    if not session_id:
        return None
    try:
        hist_res = (
            supabase.table("history")
            .select("source_id,channel,metadata")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
        for row in (hist_res.data or []):
            if _norm_channel(row.get("channel")) == "email":
                metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                delivery = metadata.get("delivery") if isinstance(metadata.get("delivery"), dict) else {}
                meta_thread = str(delivery.get("thread_id") or "").strip()
                if meta_thread and not _looks_like_uuid(meta_thread):
                    return meta_thread
                candidate = str(row.get("source_id") or "").strip()
                # In this env `history.source_id` may be an internal UUID (handoff id), not Gmail threadId.
                if candidate and not _looks_like_uuid(candidate):
                    return candidate
    except Exception as e:
        logger.warning("Could not derive email thread id from history | client_id=%s session_id=%s err=%s", client_id, session_id, e)
    return None


def _best_effort_sync_after_send(
    *,
    client_id: str,
    handoff: dict,
    handoff_id: str,
    auth_user_id: str,
    mark_resolved: bool,
) -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        handoff_status = "resolved" if mark_resolved else "in_progress"
        handoff_payload = {
            "assigned_user_id": auth_user_id,
            "status": handoff_status,
            "updated_at": now_iso,
        }
        if mark_resolved:
            handoff_payload["resolved_at"] = now_iso

        (
            supabase.table("conversation_handoff_requests")
            .update(handoff_payload)
            .eq("id", handoff_id)
            .eq("client_id", client_id)
            .execute()
        )

        alert_payload = {
            "assigned_user_id": auth_user_id,
            "status": "resolved" if mark_resolved else "acknowledged",
            "resolved_at": now_iso if mark_resolved else None,
        }
        (
            supabase.table("conversation_alerts")
            .update(alert_payload)
            .eq("client_id", client_id)
            .eq("source_handoff_request_id", handoff_id)
            .execute()
        )

        conversation_id = handoff.get("conversation_id")
        if conversation_id:
            convo_payload = {
                "assigned_user_id": auth_user_id,
                "status": "resolved" if mark_resolved else "human_in_progress",
                "updated_at": now_iso,
                "latest_message_at": now_iso,
            }
            (
                supabase.table("conversations")
                .update(convo_payload)
                .eq("id", conversation_id)
                .eq("client_id", client_id)
                .execute()
            )
    except Exception as e:
        logger.warning("Could not sync handoff status after send | handoff_id=%s err=%s", handoff_id, e)


def _best_effort_insert_human_history(
    *,
    client_id: str,
    session_id: str,
    channel: str,
    provider: str,
    message: str,
    handoff_id: str,
    delivery_meta: dict,
) -> None:
    try:
        payload = {
            "client_id": client_id,
            "session_id": session_id,
            "role": "assistant",
            "content": message,
            "channel": channel or "chat",
            "source_type": "human_agent",
            "provider": provider,
            # `history.source_id` is UUID in this environment. External provider IDs (Gmail/Meta) are not UUIDs.
            # Keep provider IDs in metadata and store the internal handoff UUID here so timeline insert never fails.
            "source_id": str(handoff_id),
            "status": "sent",
            "metadata": {
                "handoff_id": handoff_id,
                "human_agent": True,
                "delivery": delivery_meta,
                "sent_from": "inbox_handoff",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("history").insert(payload).execute()
    except Exception as e:
        logger.warning("Could not insert human agent history | handoff_id=%s err=%s", handoff_id, e)


@router.post("/conversation_handoff_requests/{handoff_id}/send_reply")
async def send_handoff_reply(handoff_id: str, payload: ConversationSendReplyInput, request: Request):
    try:
        auth_user_id = authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")
        message = str(payload.message or "").strip()
        if not message:
            raise HTTPException(status_code=422, detail="message is required")

        handoff_res = (
            supabase.table("conversation_handoff_requests")
            .select(
                "id,client_id,conversation_id,session_id,channel,status,contact_name,contact_email,contact_phone,"
                "metadata"
            )
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .maybe_single()
            .execute()
        )
        handoff = handoff_res.data if handoff_res else None
        if not handoff:
            raise HTTPException(status_code=404, detail="Handoff request not found")

        origin_channel = _norm_channel(handoff.get("channel"))
        requested_channel = _norm_channel(payload.reply_channel)
        channel = requested_channel or origin_channel
        provider = "internal"
        delivery_meta: dict = {}

        if channel == "email":
            to_email = str(handoff.get("contact_email") or "").strip().lower()
            if not to_email:
                raise HTTPException(status_code=422, detail="Handoff has no contact_email")

            subject = str(payload.subject or "").strip() or "Re: Follow-up from support"
            thread_id = _derive_email_thread_id(payload.client_id, handoff.get("session_id"), payload.thread_id)

            gmail_payload = {
                "client_id": payload.client_id,
                "to_email": to_email,
                "subject": subject,
                "html": html.escape(message).replace("\n", "<br>"),
                "purpose": "transactional",
                "policy_source": "conversation_handoff_send_reply",
                "source_id": handoff_id,
            }
            if thread_id:
                gmail_payload["thread_id"] = thread_id

            resp = await gmail_send_reply(gmail_payload, request)
            if isinstance(resp, JSONResponse) and getattr(resp, "status_code", 200) >= 400:
                body = _json_response_payload(resp)
                raise HTTPException(status_code=resp.status_code, detail=body.get("detail") or "Email send failed")

            resp_body = _json_response_payload(resp) if isinstance(resp, JSONResponse) else {}
            returned_thread_id = str(resp_body.get("thread_id") or "").strip() or None
            delivery_meta = {
                "provider": "gmail",
                "message_id": resp_body.get("message_id"),
                "thread_id": returned_thread_id or thread_id,
                "to_email": to_email,
                "subject": subject,
            }
            provider = "gmail"

        elif channel == "whatsapp":
            to_number = str(handoff.get("contact_phone") or "").strip()
            if not to_number:
                raise HTTPException(status_code=422, detail="Handoff has no contact_phone")

            # Widget-origin follow-up usually requires a template (outside active 24h chat window).
            use_whatsapp_template = (
                bool(payload.whatsapp_use_template)
                if payload.whatsapp_use_template is not None
                else origin_channel in {"widget", "chat", "email", ""}
            )

            if use_whatsapp_template:
                template_name = (
                    str(payload.whatsapp_template_name or "").strip()
                    or os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME", "").strip()
                    or "human_handoff_followup_text"
                )
                language_code = (
                    str(payload.whatsapp_template_language_code or "").strip()
                    or _default_whatsapp_template_language(handoff)
                )
                template_result = await send_whatsapp_template_for_client(
                    client_id=payload.client_id,
                    to_number=to_number,
                    template_name=template_name,
                    parameters=[message],  # expected Meta template body contains {{1}} for free text
                    language_code=language_code,
                    purpose="transactional",
                    policy_source="conversation_handoff_send_reply_template",
                    policy_source_id=handoff_id,
                )
                if not template_result.get("success"):
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "WhatsApp template send failed. Configure/approve the handoff reply template "
                            f"(e.g. {template_name} with {{1}} free-text variable). "
                            f"Provider error: {template_result.get('error')}"
                        ),
                    )

                delivery_meta = {
                    "provider": "meta_template",
                    "to_phone": to_number,
                    "template_name": template_name,
                    "language_code": language_code,
                    "meta_message_id": template_result.get("meta_message_id"),
                    "template_parameters_count": 1,
                    "origin_channel": origin_channel,
                }
                provider = "meta"
            else:
                sent = await send_whatsapp_message_for_client(
                    client_id=payload.client_id,
                    to_number=to_number,
                    message=message,
                    purpose="transactional",
                    policy_source="conversation_handoff_send_reply",
                    policy_source_id=handoff_id,
                )
                if not sent:
                    raise HTTPException(status_code=502, detail="WhatsApp send failed")

                delivery_meta = {
                    "provider": "meta",
                    "to_phone": to_number,
                    "origin_channel": origin_channel,
                    "delivery_mode": "free_text",
                }
                provider = "meta"

        elif channel in {"widget", "chat", ""}:
            raise HTTPException(
                status_code=409,
                detail="Direct send from Inbox for widget/chat is not supported yet. Choose reply_channel=email or whatsapp.",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported handoff channel: {channel}")

        session_id = str(handoff.get("session_id") or "").strip() or f"handoff:{handoff_id}"
        _best_effort_insert_human_history(
            client_id=payload.client_id,
            session_id=session_id,
            channel=channel,
            provider=provider,
            message=message,
            handoff_id=handoff_id,
            delivery_meta=delivery_meta,
        )

        _best_effort_sync_after_send(
            client_id=payload.client_id,
            handoff=handoff,
            handoff_id=handoff_id,
            auth_user_id=auth_user_id,
            mark_resolved=bool(payload.mark_resolved),
        )

        return {
            "success": True,
            "handoff_id": handoff_id,
            "channel": channel,
            "origin_channel": origin_channel,
            "provider": provider,
            "delivery": delivery_meta,
            "mark_resolved": bool(payload.mark_resolved),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error sending handoff reply")
        raise HTTPException(status_code=500, detail=f"Handoff send reply error: {e}")
