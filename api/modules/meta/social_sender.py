from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Optional

import httpx

from api.config.config import supabase
from api.security.whatsapp_token_crypto import decrypt_whatsapp_token


logger = logging.getLogger(__name__)

_MIN_GRAPH_MAJOR = 19
_DEFAULT_GRAPH_VERSION = "v22.0"


def get_meta_graph_api_version() -> str:
    raw = str(os.getenv("META_GRAPH_API_VERSION") or _DEFAULT_GRAPH_VERSION).strip()
    match = re.match(r"^v?(\d+)(?:\.(\d+))?$", raw, flags=re.IGNORECASE)
    if not match:
        return _DEFAULT_GRAPH_VERSION

    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    if major < _MIN_GRAPH_MAJOR:
        major = _MIN_GRAPH_MAJOR
        minor = 0
    return f"v{major}.{minor}"


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.isdigit():
            ts = int(raw)
            if ts > 1_000_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def is_within_messaging_window(
    last_user_message_at: datetime | str | int | float | None,
    *,
    window_hours: int = 24,
) -> bool:
    dt = _coerce_datetime(last_user_message_at)
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    age_seconds = max(0.0, (now - dt).total_seconds())
    return age_seconds <= max(1, int(window_hours)) * 3600


def _active_channel(row: dict) -> bool:
    if "is_active" in row:
        return bool(row.get("is_active"))
    if "active" in row:
        return bool(row.get("active"))
    return True


def _normalize_channel_type(channel: str) -> str:
    value = str(channel or "").strip().lower()
    if value in {"fb_messenger", "facebook_messenger"}:
        return "messenger"
    if value in {"ig", "instagram_dm"}:
        return "instagram"
    return value


def _token_from_row(row: dict, *, channel: str) -> tuple[str, str]:
    # Current DB schema stores channel credentials in `wa_token` for Meta channels.
    # Optional legacy keys are kept for compatibility with older environments.
    for key in ("wa_token", "meta_page_token", "page_access_token", "access_token"):
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        if key == "wa_token":
            try:
                value = decrypt_whatsapp_token(value)
            except Exception:
                pass
        if value:
            return value, key

    if channel == "messenger":
        env_token = (
            os.getenv("META_MESSENGER_PAGE_TOKEN")
            or os.getenv("META_PAGE_ACCESS_TOKEN")
            or ""
        ).strip()
        if env_token:
            return env_token, "env:META_MESSENGER_PAGE_TOKEN"
    if channel == "instagram":
        env_token = (
            os.getenv("META_INSTAGRAM_PAGE_TOKEN")
            or os.getenv("META_PAGE_ACCESS_TOKEN")
            or ""
        ).strip()
        if env_token:
            return env_token, "env:META_INSTAGRAM_PAGE_TOKEN"

    return "", ""


def _recipient_candidates(channel: str, recipient_id: str) -> list[str]:
    rid = str(recipient_id or "").strip()
    if not rid:
        return []

    values = [
        rid,
        f"{channel}:{rid}",
        f"meta:{rid}",
        f"meta_{channel}:{rid}",
    ]
    if channel == "messenger":
        values.extend([f"page:{rid}", f"facebook:{rid}"])
    if channel == "instagram":
        values.extend([f"ig:{rid}", f"instagram:{rid}"])

    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def resolve_social_channel_credentials(
    *,
    channel: str,
    recipient_id: str,
) -> dict[str, Any] | None:
    normalized_channel = _normalize_channel_type(channel)
    if normalized_channel not in {"messenger", "instagram"}:
        return None

    try:
        res = (
            supabase.table("channels")
            .select("*")
            .eq("type", normalized_channel)
            .execute()
        )
    except Exception as e:
        logger.warning("Could not query channels for %s: %s", normalized_channel, e)
        return None

    rows = [dict(r) for r in (res.data or []) if isinstance(r, dict)]
    if not rows:
        return None

    match: dict | None = None
    candidates = _recipient_candidates(normalized_channel, recipient_id)
    for candidate in candidates:
        for row in rows:
            if str(row.get("value") or "").strip() != candidate:
                continue
            if _active_channel(row):
                match = row
                break
        if match:
            break

    if not match:
        for candidate in candidates:
            for row in rows:
                if str(row.get("value") or "").strip() == candidate:
                    match = row
                    break
            if match:
                break

    if not match:
        return None

    token, token_source = _token_from_row(match, channel=normalized_channel)
    if not token:
        logger.warning(
            "Meta social channel missing token | channel=%s client_id=%s value=%s",
            normalized_channel,
            match.get("client_id"),
            match.get("value"),
        )
        return None

    entity_id = str(match.get("value") or "").strip()
    if ":" in entity_id:
        entity_id = entity_id.rsplit(":", 1)[-1].strip()
    if not entity_id:
        entity_id = str(recipient_id or "").strip()
    if not entity_id:
        return None

    return {
        "client_id": match.get("client_id"),
        "channel_id": match.get("id"),
        "channel_type": normalized_channel,
        "meta_entity_id": entity_id,
        "access_token": token,
        "token_source": token_source,
    }


def _compact_meta_error_response(res: httpx.Response) -> str:
    raw_text = str(res.text or "").strip()
    if not raw_text:
        return f"HTTP {res.status_code}"

    detail = raw_text
    try:
        decoded = res.json()
        if isinstance(decoded, dict):
            err = decoded.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or "").strip()
                code = str(err.get("code") or "").strip()
                subcode = str(err.get("error_subcode") or "").strip()
                err_type = str(err.get("type") or "").strip()
                parts = [
                    p
                    for p in [
                        message,
                        f"code={code}" if code else "",
                        f"subcode={subcode}" if subcode else "",
                        err_type,
                    ]
                    if p
                ]
                if parts:
                    detail = " | ".join(parts)
    except Exception:
        detail = raw_text

    return detail[:700] + ("..." if len(detail) > 700 else "")


async def send_social_text_message(
    *,
    channel: str,
    recipient_id: str,
    message: str,
    meta_entity_id: str,
    access_token: str,
    last_user_message_at: datetime | str | int | float | None = None,
    window_hours: int = 24,
    enforce_24h_window: bool = True,
) -> dict[str, Any]:
    normalized_channel = _normalize_channel_type(channel)
    if normalized_channel not in {"messenger", "instagram"}:
        return {"success": False, "error": f"unsupported_channel:{channel}"}

    rid = str(recipient_id or "").strip()
    text = str(message or "").strip()
    actor_id = str(meta_entity_id or "").strip()
    token = str(access_token or "").strip()

    if not rid or not text or not actor_id or not token:
        return {"success": False, "error": "missing_required_send_fields"}

    window_open = is_within_messaging_window(last_user_message_at, window_hours=window_hours)
    if enforce_24h_window and not window_open:
        return {
            "success": False,
            "error": "messaging_window_closed",
            "window_open": False,
            "window_hours": window_hours,
        }

    version = get_meta_graph_api_version()
    url = f"https://graph.facebook.com/{version}/{actor_id}/messages"

    payload: dict[str, Any] = {
        "recipient": {"id": rid},
        "message": {"text": text},
    }
    if normalized_channel == "messenger":
        payload["messaging_type"] = "RESPONSE"
    else:
        payload["messaging_product"] = "instagram"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            res = await client.post(url, json=payload, headers=headers)
        if res.status_code >= 400:
            return {
                "success": False,
                "status_code": res.status_code,
                "error": _compact_meta_error_response(res),
                "window_open": window_open,
                "window_hours": window_hours,
            }

        data = {}
        try:
            data = res.json() if res.text else {}
        except Exception:
            data = {}
        message_id = None
        if isinstance(data, dict):
            mids = data.get("message_id")
            if isinstance(mids, str):
                message_id = mids
            elif isinstance(data.get("message_id"), list):
                message_id = (data.get("message_id") or [None])[0]
            if not message_id:
                ids = data.get("message_id") or data.get("message_ids")
                if isinstance(ids, list):
                    message_id = ids[0] if ids else None
                elif isinstance(ids, str):
                    message_id = ids
            if not message_id:
                items = data.get("messages")
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    message_id = items[0].get("id")

        return {
            "success": True,
            "status_code": res.status_code,
            "message_id": message_id,
            "window_open": window_open,
            "window_hours": window_hours,
        }
    except Exception as e:
        logger.exception("Meta social send failed | channel=%s", normalized_channel)
        return {
            "success": False,
            "error": f"send_exception:{e}",
            "window_open": window_open,
            "window_hours": window_hours,
        }
