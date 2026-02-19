import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, status


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _state_secret() -> str:
    secret = (
        os.getenv("GOOGLE_OAUTH_STATE_SECRET")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="oauth_state_secret_not_configured",
        )
    return secret


def encode_signed_state(payload: dict) -> str:
    state_payload = dict(payload)
    state_payload["iat"] = int(time.time())
    payload_json = json.dumps(
        state_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_part = _b64url_encode(payload_json)
    sig = hmac.new(
        _state_secret().encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_part = _b64url_encode(sig)
    return f"{payload_part}.{sig_part}"


def decode_signed_state(state: str, *, max_age_seconds: int = 900) -> dict:
    if not state or "." not in state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_oauth_state",
        )

    payload_part, sig_part = state.split(".", 1)
    expected_sig = hmac.new(
        _state_secret().encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    provided_sig = _b64url_decode(sig_part)
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_oauth_state_signature",
        )

    payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    issued_at = int(payload.get("iat") or 0)
    now = int(time.time())
    if issued_at <= 0 or now - issued_at > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expired_oauth_state",
        )

    return payload
