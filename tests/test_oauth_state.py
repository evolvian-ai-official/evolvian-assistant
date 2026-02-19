import pytest
from fastapi import HTTPException

from api.oauth_state import decode_signed_state, encode_signed_state


def test_oauth_state_roundtrip(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_STATE_SECRET", "test-secret")
    token = encode_signed_state(
        {
            "client_id": "client-123",
            "return_to": "/services/calendar",
            "oauth_redirect_uri": "https://example.com/callback",
        }
    )

    payload = decode_signed_state(token, max_age_seconds=60)
    assert payload["client_id"] == "client-123"
    assert payload["return_to"] == "/services/calendar"
    assert payload["oauth_redirect_uri"] == "https://example.com/callback"
    assert "iat" in payload


def test_oauth_state_rejects_tampered_signature(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_STATE_SECRET", "test-secret")
    token = encode_signed_state({"client_id": "client-123"})
    payload_part, sig_part = token.split(".", 1)
    tampered = f"{payload_part}.a{sig_part[1:]}"

    with pytest.raises(HTTPException) as exc:
        decode_signed_state(tampered, max_age_seconds=60)

    assert exc.value.detail == "invalid_oauth_state_signature"
