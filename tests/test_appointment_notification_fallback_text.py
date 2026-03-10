import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.appointments import create_appointment as create_module
from api.appointments import cancellation_notifications as cancel_module


def test_confirmation_uses_text_fallback_when_template_missing(monkeypatch):
    calls = {}

    monkeypatch.setattr(create_module, "resolve_template_for_appointment", lambda **_kwargs: None)

    async def _fake_send_text(**kwargs):
        calls.update(kwargs)
        return True

    monkeypatch.setattr(create_module, "send_whatsapp_message_for_client", _fake_send_text)

    ok = asyncio.run(
        create_module.send_appointment_confirmation(
            {
                "id": "appt-1",
                "client_id": "client-1",
                "user_phone": "+525525277660",
                "user_email": "aldo.benitez.cortes@gmail.com",
                "recipient_language": "es",
            }
        )
    )

    assert ok is True
    assert calls.get("client_id") == "client-1"
    assert calls.get("to_number") == "+525525277660"
    assert "Tu cita fue agendada" in (calls.get("message") or "")


def test_cancellation_uses_text_fallback_when_template_missing(monkeypatch):
    calls = {}

    monkeypatch.setattr(cancel_module, "resolve_template_for_appointment", lambda **_kwargs: None)

    async def _fake_send_text(**kwargs):
        calls.update(kwargs)
        return True

    monkeypatch.setattr(
        "api.modules.whatsapp.whatsapp_sender.send_whatsapp_message_for_client",
        _fake_send_text,
    )

    ok = asyncio.run(
        cancel_module.send_appointment_cancellation_notification(
            {
                "id": "appt-old-1",
                "client_id": "client-1",
                "user_phone": "+525525277660",
                "user_email": "aldo.benitez.cortes@gmail.com",
                "recipient_language": "es",
            }
        )
    )

    assert ok is True
    assert calls.get("client_id") == "client-1"
    assert calls.get("to_number") == "+525525277660"
    assert "Tu cita fue cancelada" in (calls.get("message") or "")
