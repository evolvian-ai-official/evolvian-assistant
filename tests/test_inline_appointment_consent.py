import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
import sys
import types
import importlib


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
        "scheduled_time": datetime.now(timezone.utc),
        "user_name": "Test User",
        "user_email": "person@example.com",
        "user_phone": "+15551234567",
        "appointment_type": "general",
        "channel": "chat",
        "send_reminders": True,
        "reminders": None,
        "replace_existing": False,
        "consent_accepted_terms": True,
        "consent_accepted_email_marketing": False,
        "consent_captured_at": datetime.now(timezone.utc),
        "consent_user_agent": "pytest-inline",
    }
    base.update(overrides)
    return CreateAppointmentPayload(**base)


def test_capture_inline_contact_consent_inserts(monkeypatch):
    module = _load_create_appointment_module()

    inserted_rows = []

    class _FakeTable:
        def insert(self, payload):
            inserted_rows.append(payload)
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": "consent_123"}])

    class _FakeSupabase:
        def table(self, name: str):
            assert name == "widget_consents"
            return _FakeTable()

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    payload = _payload_with()

    consent_id = module._capture_inline_contact_consent(payload)
    assert consent_id == "consent_123"
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["accepted_terms"] is True
    assert inserted_rows[0]["accepted_email_marketing"] is False
    assert inserted_rows[0]["email"] == "person@example.com"


def test_capture_inline_contact_consent_skips_without_flags(monkeypatch):
    module = _load_create_appointment_module()

    class _FakeSupabase:
        def table(self, _name: str):
            raise AssertionError("table() should not be called when no consent flags were provided")

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    payload = _payload_with(
        consent_accepted_terms=None,
        consent_accepted_email_marketing=None,
    )

    consent_id = module._capture_inline_contact_consent(payload)
    assert consent_id is None
