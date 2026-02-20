from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import quote


DEFAULT_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _secret_key() -> bytes:
    raw = (
        os.getenv("APPOINTMENT_CANCEL_LINK_SECRET")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    return raw.encode("utf-8")


def _sign_payload(payload_part: str) -> str:
    secret = _secret_key()
    if not secret:
        return ""
    digest = hmac.new(secret, payload_part.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def generate_cancel_token(
    *,
    client_id: str,
    appointment_id: str,
    recipient_email: str | None,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    now_ts = int(time.time())
    payload = {
        "cid": str(client_id or "").strip(),
        "aid": str(appointment_id or "").strip(),
        "em": (recipient_email or "").strip().lower(),
        "exp": now_ts + max(60, int(ttl_seconds or DEFAULT_TOKEN_TTL_SECONDS)),
        "iat": now_ts,
    }
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    signature_part = _sign_payload(payload_part)
    return f"{payload_part}.{signature_part}" if signature_part else ""


def verify_cancel_token(token: str) -> dict[str, Any] | None:
    token_value = str(token or "").strip()
    if "." not in token_value:
        return None

    payload_part, signature_part = token_value.split(".", 1)
    if not payload_part or not signature_part:
        return None

    expected_signature = _sign_payload(payload_part)
    if not expected_signature:
        return None
    if not hmac.compare_digest(expected_signature, signature_part):
        return None

    try:
        payload_raw = _b64url_decode(payload_part)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if not payload.get("cid") or not payload.get("aid"):
        return None

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        return None

    return payload


def build_cancel_link(token: str) -> str:
    base_url = (
        os.getenv("EVOLVIAN_API_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://evolvian-assistant.onrender.com"
    ).rstrip("/")
    return f"{base_url}/appointments/cancel/by-link?token={quote(token or '')}"
