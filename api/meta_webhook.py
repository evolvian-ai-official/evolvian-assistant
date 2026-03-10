from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import json
import logging
import os
from typing import Any, Optional

from api.modules.assistant_rag.intent_router import process_user_message
from api.modules.assistant_rag.supabase_client import (
    get_client_id_by_channel,
    get_whatsapp_credentials,
    save_history,
)
from api.modules.meta.social_sender import (
    is_within_messaging_window,
    resolve_social_channel_credentials,
    send_social_text_message,
)
from api.modules.whatsapp.send_wa_message import send_whatsapp_message
from api.modules.whatsapp.webhook import (
    _cancel_appointment_from_whatsapp,
    _is_cancel_action,
    _normalize_whatsapp_session_phone,
)
from api.webhook_security import verify_meta_signature


router = APIRouter()
logger = logging.getLogger(__name__)

VERIFY_TOKEN = (
    os.getenv("META_WEBHOOK_VERIFY_TOKEN")
    or os.getenv("META_WHATSAPP_VERIFY_TOKEN")
    or ""
).strip()

_WINDOW_HOURS_RAW = str(os.getenv("META_SOCIAL_MESSAGING_WINDOW_HOURS") or "24").strip()
try:
    SOCIAL_MESSAGING_WINDOW_HOURS = max(1, int(_WINDOW_HOURS_RAW))
except Exception:
    SOCIAL_MESSAGING_WINDOW_HOURS = 24

if not VERIFY_TOKEN:
    if os.getenv("ENV") == "prod":
        logger.error("META_WEBHOOK_VERIFY_TOKEN is not configured.")
    else:
        logger.warning("META_WEBHOOK_VERIFY_TOKEN is not configured (dev mode).")


def _extract_whatsapp_message_text(msg: dict) -> str | None:
    message_type = msg.get("type")

    if message_type == "text":
        return msg.get("text", {}).get("body")

    if message_type == "interactive":
        interactive = msg.get("interactive") or {}
        button = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}
        return (
            button.get("title")
            or button.get("id")
            or list_reply.get("title")
            or list_reply.get("id")
        )

    if message_type == "button":
        button = msg.get("button") or {}
        return button.get("text") or button.get("payload")

    return None


def _extract_social_message_text(event: dict) -> str | None:
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    postback = event.get("postback") if isinstance(event.get("postback"), dict) else {}

    text = str(message.get("text") or "").strip()
    if text:
        return text

    quick_reply = message.get("quick_reply") if isinstance(message.get("quick_reply"), dict) else {}
    quick_text = str(quick_reply.get("payload") or "").strip()
    if quick_text:
        return quick_text

    postback_text = str(postback.get("title") or postback.get("payload") or "").strip()
    if postback_text:
        return postback_text

    return None


def _safe_social_timestamp(event: dict) -> Optional[datetime]:
    raw = event.get("timestamp")
    try:
        if raw is None:
            return None
        ts = float(raw)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _resolve_social_context(
    *,
    preferred_channel: str,
    recipient_id: str,
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    preferred = str(preferred_channel or "").strip().lower()
    candidates = [preferred] + [c for c in ("messenger", "instagram") if c != preferred]
    for channel in candidates:
        creds = resolve_social_channel_credentials(channel=channel, recipient_id=recipient_id)
        if creds and creds.get("client_id"):
            return channel, creds
    return None, None


async def _handle_whatsapp_message(value: dict, msg: dict) -> dict[str, Any]:
    user_phone = str(msg.get("from") or "").strip()
    text = _extract_whatsapp_message_text(msg)
    if not user_phone or not text:
        return {"status": "ignored"}

    business_phone = str((value.get("metadata") or {}).get("display_phone_number") or "").strip()
    if not business_phone:
        return {"status": "missing_business_phone"}
    formatted_value = f"whatsapp:+{business_phone.lstrip('+')}"

    client_id = get_client_id_by_channel("whatsapp", formatted_value)
    if not client_id or not isinstance(client_id, str):
        return {"status": "client_not_found"}

    try:
        credentials = get_whatsapp_credentials(client_id)
    except Exception:
        return {"status": "credentials_not_found"}

    message_type = str(msg.get("type") or "")
    if _is_cancel_action(message_type, msg, text):
        try:
            _, response = await _cancel_appointment_from_whatsapp(client_id, user_phone)
        except Exception:
            logger.exception("Error cancelling appointment from WhatsApp webhook")
            response = "⚠️ No pude cancelar tu cita en este momento. Intenta de nuevo."
    else:
        normalized_session_phone = _normalize_whatsapp_session_phone(user_phone) or user_phone
        session_id = f"whatsapp-{normalized_session_phone}"
        response = await process_user_message(
            client_id=client_id,
            session_id=session_id,
            message=text,
            channel="whatsapp",
            provider="meta",
        )

    normalized_phone = user_phone
    if normalized_phone.startswith("521"):
        normalized_phone = "52" + normalized_phone[3:]

    if response:
        sent = send_whatsapp_message(
            to_number=f"+{normalized_phone}",
            message=str(response),
            token=credentials["wa_token"],
            phone_id=credentials["wa_phone_id"],
        )
        if not sent:
            return {"status": "send_failed", "channel": "whatsapp"}

    return {"status": "ok", "channel": "whatsapp"}


async def _handle_social_event(
    *,
    preferred_channel: str,
    entry: dict,
    event: dict,
) -> dict[str, Any]:
    message_block = event.get("message") if isinstance(event.get("message"), dict) else {}
    if bool(message_block.get("is_echo")):
        return {"status": "ignored_echo"}

    sender_id = str(((event.get("sender") or {}).get("id")) or "").strip()
    recipient_id = str(((event.get("recipient") or {}).get("id")) or entry.get("id") or "").strip()
    text = _extract_social_message_text(event)

    if not sender_id or not recipient_id or not text:
        return {"status": "ignored"}

    channel, creds = _resolve_social_context(
        preferred_channel=preferred_channel,
        recipient_id=recipient_id,
    )
    if not channel or not creds:
        return {"status": "client_not_found", "recipient_id": recipient_id}

    client_id = str(creds.get("client_id") or "").strip()
    if not client_id:
        return {"status": "client_not_found", "recipient_id": recipient_id}

    session_id = f"{channel}-{sender_id}"
    event_ts = _safe_social_timestamp(event)
    if event_ts and not is_within_messaging_window(
        event_ts,
        window_hours=SOCIAL_MESSAGING_WINDOW_HOURS,
    ):
        save_history(
            client_id=client_id,
            session_id=session_id,
            role="user",
            content=text,
            channel=channel,
            provider="meta",
            metadata={
                "meta_policy": {
                    "event": "messaging_window_closed_stale_event",
                    "window_hours": SOCIAL_MESSAGING_WINDOW_HOURS,
                }
            },
        )
        return {"status": "window_closed", "channel": channel}

    response = await process_user_message(
        client_id=client_id,
        session_id=session_id,
        message=text,
        channel=channel,
        provider="meta",
    )

    if not response:
        return {"status": "no_reply", "channel": channel}

    send_result = await send_social_text_message(
        channel=channel,
        recipient_id=sender_id,
        message=str(response),
        meta_entity_id=str(creds.get("meta_entity_id") or recipient_id),
        access_token=str(creds.get("access_token") or ""),
        last_user_message_at=event_ts or datetime.now(timezone.utc),
        window_hours=SOCIAL_MESSAGING_WINDOW_HOURS,
        enforce_24h_window=True,
    )
    if not send_result.get("success"):
        logger.warning(
            "Meta social send failed | channel=%s client_id=%s sender=%s error=%s",
            channel,
            client_id,
            sender_id,
            send_result.get("error"),
        )
        return {
            "status": "send_failed",
            "channel": channel,
            "error": send_result.get("error"),
        }

    return {"status": "ok", "channel": channel}


@router.get("/webhooks/meta")
def verify_webhook(request: Request):
    if not VERIFY_TOKEN:
        return PlainTextResponse(content="Webhook verify token is not configured", status_code=503)

    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    return PlainTextResponse(content="Verification token mismatch", status_code=403)


@router.post("/webhooks/meta")
async def receive_meta_messages(request: Request):
    try:
        raw_body = await request.body()
        verify_meta_signature(request, raw_body)
        data = json.loads(raw_body.decode("utf-8") or "{}")

        object_type = str(data.get("object") or "").strip().lower()
        entries = data.get("entry") or []
        if not isinstance(entries, list) or not entries:
            return JSONResponse(content={"status": "no_message"}, status_code=200)

        results: list[dict[str, Any]] = []

        if object_type == "whatsapp_business_account":
            for entry in entries:
                changes = entry.get("changes") if isinstance(entry, dict) else []
                if not isinstance(changes, list):
                    continue
                for change in changes:
                    value = change.get("value") if isinstance(change, dict) else {}
                    if not isinstance(value, dict):
                        continue
                    messages = value.get("messages") or []
                    for msg in messages:
                        if isinstance(msg, dict):
                            results.append(await _handle_whatsapp_message(value, msg))

        elif object_type in {"page", "instagram"}:
            preferred_channel = "instagram" if object_type == "instagram" else "messenger"
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                events = entry.get("messaging") or []
                if not isinstance(events, list):
                    continue
                for event in events:
                    if isinstance(event, dict):
                        results.append(
                            await _handle_social_event(
                                preferred_channel=preferred_channel,
                                entry=entry,
                                event=event,
                            )
                        )
        else:
            return JSONResponse(
                content={"status": "ignored_object", "object": object_type or None},
                status_code=200,
            )

        if not results:
            return JSONResponse(content={"status": "no_message"}, status_code=200)

        return JSONResponse(
            content={
                "status": "ok",
                "processed": len(results),
                "by_status": _status_counts(results),
            },
            status_code=200,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error processing Meta webhook")
        return JSONResponse(status_code=500, content={"error": "internal_server_error"})
