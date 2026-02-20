from api.appointments.cancel_link_tokens import generate_cancel_token, verify_cancel_token


def test_cancel_token_roundtrip():
    token = generate_cancel_token(
        client_id="client-123",
        appointment_id="appointment-456",
        recipient_email="user@example.com",
        ttl_seconds=3600,
    )
    assert token

    payload = verify_cancel_token(token)
    assert payload is not None
    assert payload["cid"] == "client-123"
    assert payload["aid"] == "appointment-456"
    assert payload["em"] == "user@example.com"


def test_cancel_token_rejects_tampering():
    token = generate_cancel_token(
        client_id="client-123",
        appointment_id="appointment-456",
        recipient_email="user@example.com",
        ttl_seconds=3600,
    )
    assert token

    tampered = f"{token[:-1]}x"
    assert verify_cancel_token(tampered) is None
