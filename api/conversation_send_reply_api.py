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


def _default_whatsapp_handoff_template_name(language_code: str) -> str:
    normalized = str(language_code or "").strip().lower()
    if normalized.startswith("en"):
        return (
            os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_EN", "").strip()
            or os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME", "").strip()
            or "human_handoff_followup_text_en"
        )
    if normalized.startswith("es"):
        return (
            os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_ES", "").strip()
            or os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME", "").strip()
            or "human_handoff_followup_text_es"
        )
    return (
        os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME", "").strip()
        or "human_handoff_followup_text_es"
    )


def _normalize_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _phone_candidates(value: str | None) -> list[str]:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return []

    candidates = {digits}
    if digits.startswith("521") and len(digits) > 3:
        candidates.add(f"52{digits[3:]}")
    if digits.startswith("52") and len(digits) > 2:
        candidates.add(f"521{digits[2:]}")

    ordered = sorted(candidates, key=lambda x: (len(x), x))
    return ordered


def _build_whatsapp_session_candidates(session_id: str | None, phone: str | None) -> list[str]:
    values: set[str] = set()
    base = str(session_id or "").strip()
    if base:
        values.add(base)

    for candidate in _phone_candidates(phone):
        values.add(f"whatsapp-{candidate}")
        values.add(f"whatsapp-+{candidate}")

    return sorted(values)


def _resolve_whatsapp_free_text_window(
    *,
    client_id: str,
    session_id: str | None,
    contact_phone: str | None,
) -> dict:
    window_hours_raw = os.getenv("WHATSAPP_FREE_TEXT_WINDOW_HOURS", "24").strip()
    try:
        window_hours = max(1, int(window_hours_raw))
    except Exception:
        window_hours = 24

    result = {
        "window_hours": window_hours,
        "is_open": False,
        "last_user_message_at": None,
        "matched_session_id": None,
    }

    candidates = _build_whatsapp_session_candidates(session_id, contact_phone)
    if not candidates:
        return result

    try:
        res = (
            supabase.table("history")
            .select("created_at,session_id")
            .eq("client_id", client_id)
            .eq("channel", "whatsapp")
            .eq("role", "user")
            .in_("session_id", candidates)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
    except Exception as e:
        logger.warning("Could not resolve WhatsApp free-text window | client_id=%s err=%s", client_id, e)
        return result

    if not row:
        return result

    last_at_raw = row.get("created_at")
    last_at = _normalize_iso_datetime(last_at_raw)
    if not last_at:
        return result
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_seconds = (now - last_at).total_seconds()
    is_open = age_seconds <= (window_hours * 3600)

    result["is_open"] = bool(is_open)
    result["last_user_message_at"] = str(last_at_raw or "")
    result["matched_session_id"] = row.get("session_id")
    return result


def _candidate_whatsapp_template_names(language_code: str, explicit_name: str | None = None) -> list[str]:
    names: list[str] = []

    def _push(value: str | None) -> None:
        v = str(value or "").strip()
        if v and v not in names:
            names.append(v)

    normalized = str(language_code or "").strip().lower()
    is_en = normalized.startswith("en")

    _push(explicit_name)
    if is_en:
        _push(os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_EN"))
        _push(os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME"))
        _push("human_handoff_reply_en")
        _push("human_handoff_followup_text_en")
    else:
        _push(os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_ES"))
        _push(os.getenv("WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME"))
        _push("respuesta_equipo_humano_es")
        _push("human_handoff_reply_es")
        _push("human_handoff_followup_text_es")

    return names


def _is_missing_template_translation_error(template_result: dict) -> bool:
    raw_error = str((template_result or {}).get("error") or "").lower()
    if not raw_error:
        return False
    return (
        '"code":132001' in raw_error
        or "template name does not exist in the translation" in raw_error
        or "does not exist in en_" in raw_error
        or "does not exist in es_" in raw_error
    )


async def _send_whatsapp_template_with_fallback(
    *,
    client_id: str,
    to_number: str,
    initial_template_name: str,
    language_code: str,
    message: str,
    purpose: str,
    policy_source: str,
    policy_source_id: str,
) -> dict:
    candidates = _candidate_whatsapp_template_names(language_code, initial_template_name)
    attempted: list[str] = []
    last_result: dict | None = None

    for candidate in candidates:
        attempted.append(candidate)
        result = await send_whatsapp_template_for_client(
            client_id=client_id,
            to_number=to_number,
            template_name=candidate,
            parameters=[message],  # expected Meta template body contains {{1}} for free text
            language_code=language_code,
            purpose=purpose,
            policy_source=policy_source,
            policy_source_id=policy_source_id,
        )
        last_result = result
        if result.get("success"):
            result["_resolved_template_name"] = candidate
            result["_attempted_template_names"] = attempted
            return result
        if not _is_missing_template_translation_error(result):
            break

    if not last_result:
        last_result = {"success": False, "error": "No WhatsApp template candidates configured"}
    last_result["_attempted_template_names"] = attempted
    return last_result


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
    except Exception as e:
        logger.warning("Could not derive email thread id from history | client_id=%s session_id=%s err=%s", client_id, session_id, e)
    return None


def _resolve_handoff_email_thread_id(
    *,
    client_id: str,
    session_id: str | None,
    explicit_thread_id: str | None,
    origin_channel: str | None,
) -> tuple[Optional[str], str]:
    explicit = str(explicit_thread_id or "").strip()
    if explicit:
        return explicit, "explicit"

    origin = _norm_channel(origin_channel)
    if origin != "email":
        return None, "new_message_non_email_origin"

    derived = _derive_email_thread_id(client_id, session_id, None)
    if derived:
        return derived, "derived_from_email_history"
    return None, "new_message_no_thread"


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
            thread_id, thread_mode = _resolve_handoff_email_thread_id(
                client_id=payload.client_id,
                session_id=handoff.get("session_id"),
                explicit_thread_id=payload.thread_id,
                origin_channel=origin_channel,
            )

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
                "thread_mode": thread_mode,
                "to_email": to_email,
                "subject": subject,
            }
            provider = "gmail"

        elif channel == "whatsapp":
            to_number = str(handoff.get("contact_phone") or "").strip()
            if not to_number:
                raise HTTPException(status_code=422, detail="Handoff has no contact_phone")

            auto_from_whatsapp = origin_channel == "whatsapp"
            force_template = bool(payload.whatsapp_use_template) or not auto_from_whatsapp
            allow_free_text_first = not force_template
            force_free_text_only = allow_free_text_first and payload.whatsapp_use_template is False
            whatsapp_window = (
                _resolve_whatsapp_free_text_window(
                    client_id=payload.client_id,
                    session_id=handoff.get("session_id"),
                    contact_phone=to_number,
                )
                if allow_free_text_first
                else {
                    "window_hours": int(os.getenv("WHATSAPP_FREE_TEXT_WINDOW_HOURS", "24") or 24),
                    "is_open": None,
                    "last_user_message_at": None,
                    "matched_session_id": None,
                }
            )
            language_code = (
                str(payload.whatsapp_template_language_code or "").strip()
                or _default_whatsapp_template_language(handoff)
            )
            template_name = (
                str(payload.whatsapp_template_name or "").strip()
                or _default_whatsapp_handoff_template_name(language_code)
            )

            if allow_free_text_first:
                sent = await send_whatsapp_message_for_client(
                    client_id=payload.client_id,
                    to_number=to_number,
                    message=message,
                    purpose="transactional",
                    policy_source="conversation_handoff_send_reply",
                    policy_source_id=handoff_id,
                )
                if sent:
                    delivery_meta = {
                        "provider": "meta",
                        "to_phone": to_number,
                        "origin_channel": origin_channel,
                        "delivery_mode": "free_text",
                        "window_open": bool(whatsapp_window.get("is_open")),
                        "window_hours": whatsapp_window.get("window_hours"),
                        "last_user_whatsapp_message_at": whatsapp_window.get("last_user_message_at"),
                        "window_session_id": whatsapp_window.get("matched_session_id"),
                    }
                    provider = "meta"
                else:
                    if force_free_text_only:
                        raise HTTPException(status_code=502, detail="WhatsApp send failed")
                    template_result = await _send_whatsapp_template_with_fallback(
                        client_id=payload.client_id,
                        to_number=to_number,
                        initial_template_name=template_name,
                        language_code=language_code,
                        message=message,
                        purpose="transactional",
                        policy_source="conversation_handoff_send_reply_template",
                        policy_source_id=handoff_id,
                    )
                    if not template_result.get("success"):
                        attempted = template_result.get("_attempted_template_names") or []
                        attempted_hint = f" Attempted: {', '.join(attempted)}." if attempted else ""
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                "WhatsApp template send failed. Configure/approve the handoff reply template "
                                f"(e.g. {template_name} with {{1}} free-text variable)."
                                f"{attempted_hint} Provider error: {template_result.get('error')}"
                            ),
                        )
                    resolved_template_name = str(
                        template_result.get("_resolved_template_name") or template_name
                    ).strip() or template_name

                    delivery_meta = {
                        "provider": "meta_template",
                        "to_phone": to_number,
                        "template_name": resolved_template_name,
                        "language_code": language_code,
                        "meta_message_id": template_result.get("meta_message_id"),
                        "template_parameters_count": 1,
                        "origin_channel": origin_channel,
                        "window_open": bool(whatsapp_window.get("is_open")),
                        "window_hours": whatsapp_window.get("window_hours"),
                        "last_user_whatsapp_message_at": whatsapp_window.get("last_user_message_at"),
                        "window_session_id": whatsapp_window.get("matched_session_id"),
                        "delivery_mode": "free_text_fallback_to_template",
                    }
                    provider = "meta"
            else:
                template_result = await _send_whatsapp_template_with_fallback(
                    client_id=payload.client_id,
                    to_number=to_number,
                    initial_template_name=template_name,
                    language_code=language_code,
                    message=message,
                    purpose="transactional",
                    policy_source="conversation_handoff_send_reply_template",
                    policy_source_id=handoff_id,
                )
                if not template_result.get("success"):
                    attempted = template_result.get("_attempted_template_names") or []
                    attempted_hint = f" Attempted: {', '.join(attempted)}." if attempted else ""
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "WhatsApp template send failed. Configure/approve the handoff reply template "
                            f"(e.g. {template_name} with {{1}} free-text variable)."
                            f"{attempted_hint} Provider error: {template_result.get('error')}"
                        ),
                    )
                resolved_template_name = str(
                    template_result.get("_resolved_template_name") or template_name
                ).strip() or template_name

                delivery_meta = {
                    "provider": "meta_template",
                    "to_phone": to_number,
                    "template_name": resolved_template_name,
                    "language_code": language_code,
                    "meta_message_id": template_result.get("meta_message_id"),
                    "template_parameters_count": 1,
                    "origin_channel": origin_channel,
                    "window_open": whatsapp_window.get("is_open"),
                    "window_hours": whatsapp_window.get("window_hours"),
                    "last_user_whatsapp_message_at": whatsapp_window.get("last_user_message_at"),
                    "window_session_id": whatsapp_window.get("matched_session_id"),
                    "delivery_mode": "template",
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
