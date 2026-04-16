import asyncio
import importlib
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_create_appointment_module():
    if "babel" not in sys.modules:
        fake_babel = types.ModuleType("babel")
        fake_dates = types.ModuleType("babel.dates")
        fake_dates.format_datetime = lambda *args, **kwargs: "formatted"
        fake_babel.dates = fake_dates
        sys.modules["babel"] = fake_babel
        sys.modules["babel.dates"] = fake_dates
    return importlib.import_module("api.appointments.create_appointment")


def _payload_with(**overrides):
    module = _load_create_appointment_module()
    CreateAppointmentPayload = module.CreateAppointmentPayload

    base = {
        "client_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "scheduled_time": datetime.now(timezone.utc) + timedelta(days=1),
        "user_name": "Test User",
        "user_email": "person@example.com",
        "user_phone": "+15551234567",
        "appointment_type": "general",
        "channel": "manual",
        "send_reminders": False,
        "reminders": None,
        "replace_existing": False,
    }
    base.update(overrides)
    return CreateAppointmentPayload(**base)


def test_create_appointment_blocks_manual_creation_when_feature_disabled(monkeypatch):
    module = _load_create_appointment_module()

    monkeypatch.setattr(module, "client_can_use_manual_appointment_creation", lambda _client_id: False)
    monkeypatch.setattr(module, "is_calendar_active_for_client", lambda _client_id: True)

    result = asyncio.run(module.create_appointment(_payload_with(channel="manual")))

    assert result["success"] is False
    assert result["manual_creation_disabled"] is True
    assert "not enabled for this plan" in result["message"]


def test_create_appointment_manual_gate_does_not_block_widget_flow(monkeypatch):
    module = _load_create_appointment_module()

    monkeypatch.setattr(module, "client_can_use_manual_appointment_creation", lambda _client_id: False)
    monkeypatch.setattr(module, "is_calendar_active_for_client", lambda _client_id: False)

    result = asyncio.run(module.create_appointment(_payload_with(channel="widget")))

    assert result["success"] is False
    assert result["calendar_inactive"] is True
    assert "manual_creation_disabled" not in result
