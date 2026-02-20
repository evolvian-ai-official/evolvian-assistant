from types import SimpleNamespace
import sys
import types

import pytest
from fastapi import HTTPException

# Test sandbox fallback: some environments don't have Babel installed.
if "babel" not in sys.modules:
    babel_module = types.ModuleType("babel")
    babel_dates_module = types.ModuleType("babel.dates")

    def _noop_format_datetime(*_args, **_kwargs):
        return ""

    def _noop_format_date(*_args, **_kwargs):
        return ""

    babel_dates_module.format_datetime = _noop_format_datetime
    babel_dates_module.format_date = _noop_format_date
    babel_module.dates = babel_dates_module
    sys.modules["babel"] = babel_module
    sys.modules["babel.dates"] = babel_dates_module

from api import chat_widget_api as widget_api


class _FakeQuery:
    def __init__(self, data_source):
        self._data_source = data_source
        self._filters = {}

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def gte(self, key, value):
        self._filters[key] = value
        return self

    def in_(self, key, values):
        self._filters[key] = list(values or [])
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data_source(self._filters))


class _FakeSupabase:
    def __init__(self, data_source):
        self._data_source = data_source

    def table(self, table_name):
        assert table_name == "appointments"
        return _FakeQuery(self._data_source)


def test_find_active_widget_appointment_matches_by_email(monkeypatch):
    rows = [
        {
            "id": "appt-later",
            "status": "confirmed",
            "user_name": "Aldo Nicolas",
            "user_email": "aldo@example.com",
            "user_phone": "+5215550001111",
            "scheduled_time": "2026-03-01T11:00:00+00:00",
            "appointment_type": "Consulta",
        },
        {
            "id": "appt-sooner",
            "status": "scheduled",
            "user_name": "Aldo Nicolas",
            "user_email": "aldo@example.com",
            "user_phone": "+5215550001111",
            "scheduled_time": "2026-02-25T11:00:00+00:00",
            "appointment_type": "Consulta",
        },
    ]

    def data_source(filters):
        assert filters.get("status") == ["confirmed", "scheduled", "pending"]
        return rows

    monkeypatch.setattr(widget_api, "supabase", _FakeSupabase(data_source))

    result = widget_api._find_active_widget_appointment(
        client_id="client-1",
        user_email="ALDO@example.com",
        user_phone=None,
    )

    assert result is not None
    assert result["id"] == "appt-sooner"


def test_find_active_widget_appointment_matches_by_normalized_phone(monkeypatch):
    rows = [
        {
            "id": "appt-phone",
            "status": "pending",
            "user_name": "Aldo Nicolas",
            "user_email": "aldo@example.com",
            "user_phone": "+5215550001111",
            "scheduled_time": "2026-02-25T11:00:00+00:00",
            "appointment_type": "Consulta",
        },
    ]

    def data_source(filters):
        assert filters.get("status") == ["confirmed", "scheduled", "pending"]
        return rows

    monkeypatch.setattr(widget_api, "supabase", _FakeSupabase(data_source))

    result = widget_api._find_active_widget_appointment(
        client_id="client-1",
        user_email=None,
        user_phone="+52 1 555-000-1111",
    )

    assert result is not None
    assert result["id"] == "appt-phone"


def test_find_active_widget_appointment_ignores_name_mismatch(monkeypatch):
    rows = [
        {
            "id": "appt-other",
            "status": "confirmed",
            "user_name": "Otra Persona",
            "user_email": "aldo@example.com",
            "user_phone": "+5215550001111",
            "scheduled_time": "2026-02-25T11:00:00+00:00",
            "appointment_type": "Consulta",
        },
    ]

    def data_source(filters):
        assert filters.get("status") == ["confirmed", "scheduled", "pending"]
        return rows

    monkeypatch.setattr(widget_api, "supabase", _FakeSupabase(data_source))

    result = widget_api._find_active_widget_appointment(
        client_id="client-1",
        user_email="aldo@example.com",
        user_phone=None,
    )

    assert result is not None
    assert result["id"] == "appt-other"


def test_find_active_widget_appointment_requires_contact():
    with pytest.raises(HTTPException) as exc:
        widget_api._find_active_widget_appointment(
            client_id="client-1",
            user_email=None,
            user_phone=None,
        )

    assert exc.value.status_code == 400
    assert "Provide at least email or phone" in str(exc.value.detail)
