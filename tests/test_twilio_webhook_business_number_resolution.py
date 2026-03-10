import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import twilio_webhook


class _FakeTwilioRequest:
    def __init__(self, body: str, from_number: str, to_number: str):
        self._form = {"Body": body, "From": from_number, "To": to_number}
        self.headers = {}

    async def form(self):
        return self._form


def test_twilio_webhook_prefers_business_to_number_for_client_resolution(monkeypatch):
    monkeypatch.setattr(twilio_webhook, "verify_twilio_signature", lambda *_a, **_k: None)

    calls = []

    def _fake_get_client_id_by_channel(channel_type: str, value: str):
        calls.append((channel_type, value))
        if value == "whatsapp:+15550001111":
            return "client-123"
        return None

    async def _fake_process_user_message(*_args, **_kwargs):
        return "AGENDAR_OK"

    monkeypatch.setattr(twilio_webhook, "get_client_id_by_channel", _fake_get_client_id_by_channel)
    monkeypatch.setattr(twilio_webhook, "process_user_message", _fake_process_user_message)

    req = _FakeTwilioRequest(
        body="Quiero agendar una cita",
        from_number="whatsapp:+19998887777",
        to_number="whatsapp:+15550001111",
    )

    response = asyncio.run(
        twilio_webhook.twilio_webhook(
            req,
            Body="Quiero agendar una cita",
            From="whatsapp:+19998887777",
            To="whatsapp:+15550001111",
        )
    )

    body = response.body.decode("utf-8")
    assert "AGENDAR_OK" in body
    assert calls, "Expected channel lookup calls"
    # First lookup should use To/business number candidate.
    assert calls[0] == ("whatsapp", "whatsapp:+15550001111")
