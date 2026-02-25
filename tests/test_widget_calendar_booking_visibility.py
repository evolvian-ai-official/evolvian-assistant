import asyncio
from datetime import datetime, timedelta, timezone
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


class _FakeBookQuery:
    def select(self, _fields):
        return self

    def eq(self, _key, _value):
        return self

    def in_(self, _key, _values):
        return self

    def gte(self, _key, _value):
        return self

    def lt(self, _key, _value):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def table(self, table_name):
        assert table_name == "appointments"
        return _FakeBookQuery()


class _FakeAvailabilityQuery:
    def __init__(self, data_source):
        self._data_source = data_source
        self._filters = {}

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def in_(self, key, values):
        self._filters[key] = list(values or [])
        return self

    def gte(self, key, value):
        self._filters[key] = value
        return self

    def lte(self, key, value):
        self._filters[key] = value
        return self

    def execute(self):
        return SimpleNamespace(data=self._data_source(self._filters))


class _FakeAvailabilitySupabase:
    def __init__(self, data_source):
        self._data_source = data_source

    def table(self, table_name):
        assert table_name == "appointments"
        return _FakeAvailabilityQuery(self._data_source)


def _build_payload():
    scheduled = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat() + "Z"
    return widget_api.WidgetBookRequest(
        public_client_id="public-client-1",
        scheduled_time=scheduled,
        user_name="Aldo",
        user_email="aldo@example.com",
        user_phone="+525551234567",
        session_id=None,
    )


def test_widget_booking_allows_manual_calendar_when_chat_ai_scheduling_is_disabled(monkeypatch):
    monkeypatch.setattr(widget_api, "supabase", _FakeSupabase())
    monkeypatch.setattr(
        widget_api,
        "get_client_id_from_public_client_id",
        lambda _public_client_id: "2d9987c0-a08b-41a3-bd90-1f11bf099849",
    )
    monkeypatch.setattr(
        widget_api,
        "_get_widget_calendar_config",
        lambda _client_id: {
            "calendar_status": "active",
            "show_agenda_in_chat_widget": True,
            "ai_scheduling_chat_enabled": False,
            "timezone": "UTC",
        },
    )

    async def _fake_create_appointment(payload):
        assert payload.channel == "widget"
        return {
            "success": True,
            "appointment_id": "appt-1",
            "scheduled_time": str(payload.scheduled_time),
        }

    monkeypatch.setattr(widget_api, "create_appointment_route", _fake_create_appointment)

    result = asyncio.run(widget_api.book_widget_calendar(_build_payload()))
    assert result["success"] is True
    assert result["appointment_id"] == "appt-1"


def test_widget_booking_rejects_when_widget_agenda_is_hidden(monkeypatch):
    monkeypatch.setattr(widget_api, "supabase", _FakeSupabase())
    monkeypatch.setattr(
        widget_api,
        "get_client_id_from_public_client_id",
        lambda _public_client_id: "2d9987c0-a08b-41a3-bd90-1f11bf099849",
    )
    monkeypatch.setattr(
        widget_api,
        "_get_widget_calendar_config",
        lambda _client_id: {
            "calendar_status": "active",
            "show_agenda_in_chat_widget": False,
            "ai_scheduling_chat_enabled": True,
            "timezone": "UTC",
        },
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(widget_api.book_widget_calendar(_build_payload()))

    assert exc.value.status_code == 403
    assert "hidden in chat widget" in str(exc.value.detail)


def test_widget_availability_hides_pending_confirmation_slots(monkeypatch):
    slot_dt = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    )
    slot_iso = slot_dt.isoformat()
    slot_date = slot_dt.strftime("%Y-%m-%d")

    def _data_source(filters):
        assert "pending_confirmation" in (filters.get("status") or [])
        return [{"scheduled_time": slot_iso}]

    monkeypatch.setattr(widget_api, "supabase", _FakeAvailabilitySupabase(_data_source))
    monkeypatch.setattr(
        widget_api,
        "get_client_id_from_public_client_id",
        lambda _public_client_id: "client-1",
    )
    monkeypatch.setattr(
        widget_api,
        "_get_widget_calendar_config",
        lambda _client_id: {
            "calendar_status": "active",
            "show_agenda_in_chat_widget": True,
            "timezone": "UTC",
            "selected_days": set(range(7)),
            "start_time": "09:00",
            "end_time": "12:00",
            "slot_duration_minutes": 30,
            "buffer_minutes": 0,
            "min_notice_hours": 0,
            "allow_same_day": True,
        },
    )

    result = widget_api.get_widget_calendar_availability(
        public_client_id="public-client-1",
        from_date=slot_date,
        to_date=slot_date,
    )

    slot_starts = {slot["start_iso"] for slot in result["slots"]}
    assert slot_iso not in slot_starts


def test_widget_booking_conflict_precheck_blocks_pending_confirmation(monkeypatch):
    monkeypatch.setattr(widget_api, "get_client_id_from_public_client_id", lambda _public_client_id: "client-1")
    monkeypatch.setattr(
        widget_api,
        "_get_widget_calendar_config",
        lambda _client_id: {
            "calendar_status": "active",
            "show_agenda_in_chat_widget": True,
            "timezone": "UTC",
        },
    )

    class _ConflictQuery:
        def __init__(self):
            self.filters = {}

        def select(self, _fields):
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def in_(self, key, values):
            self.filters[key] = list(values or [])
            return self

        def gte(self, key, value):
            self.filters[key] = value
            return self

        def lt(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _value):
            return self

        def execute(self):
            assert "pending_confirmation" in (self.filters.get("status") or [])
            return SimpleNamespace(data=[{"id": "appt-conflict"}])

    class _ConflictSupabase:
        def table(self, table_name):
            assert table_name == "appointments"
            return _ConflictQuery()

    async def _unexpected_create(_payload):
        raise AssertionError("create_appointment_route should not be called when conflict exists")

    monkeypatch.setattr(widget_api, "supabase", _ConflictSupabase())
    monkeypatch.setattr(widget_api, "create_appointment_route", _unexpected_create)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(widget_api.book_widget_calendar(_build_payload()))

    assert exc.value.status_code == 409
    assert "no longer available" in str(exc.value.detail)
