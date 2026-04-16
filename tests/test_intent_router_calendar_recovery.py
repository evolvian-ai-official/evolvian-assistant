import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import intent_router


class _FakeCalendarSettingsQuery:
    def __init__(self):
        self._maybe_single = False

    def select(self, _fields):
        return self

    def eq(self, _key, _value):
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def execute(self):
        row = {
            "calendar_status": "active",
            "ai_scheduling_chat_enabled": True,
            "ai_scheduling_whatsapp_enabled": True,
        }
        return SimpleNamespace(data=row if self._maybe_single else [row])


class _FakeSupabase:
    def table(self, name):
        if name != "calendar_settings":
            raise AssertionError(f"Unexpected table lookup: {name}")
        return _FakeCalendarSettingsQuery()


def test_calendar_route_recovers_when_state_is_missing(monkeypatch):
    fake_calendar_features = types.ModuleType("api.utils.calendar_feature_flags")
    fake_calendar_features.client_can_use_calendar_ai_for_channel = lambda _client_id, _channel: True
    monkeypatch.setitem(sys.modules, "api.utils.calendar_feature_flags", fake_calendar_features)

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())
    monkeypatch.setattr(intent_router, "detect_intent_to_schedule", lambda _message: False)
    monkeypatch.setattr(intent_router, "get_state", lambda _client_id, _session_id: {})
    monkeypatch.setattr(intent_router, "_has_recent_appointment_history", lambda *_a, **_k: True)

    upserts = []

    def _upsert_state(client_id, session_id, state):
        upserts.append((client_id, session_id, dict(state or {})))

    async def _calendar_handler(client_id, _message, _session_id, _channel, _lang):
        return f"AGENDAR_RECOVERED|{client_id}"

    def _unexpected_ask_question(*_args, **_kwargs):
        raise AssertionError("ask_question should not run when calendar route is recovered")

    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "_calendar_handler", _calendar_handler)
    monkeypatch.setattr(intent_router, "ask_question", _unexpected_ask_question)
    monkeypatch.setattr(intent_router, "save_history", lambda *_a, **_k: None)

    answer = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id="session-1",
            message="mañana a las 9:00",
            channel="chat",
            provider="widget",
        )
    )

    assert answer == "AGENDAR_RECOVERED|client-1"
    assert upserts, "Expected recovered state to be persisted"
    recovered_state = upserts[-1][2]
    assert recovered_state.get("intent") == "calendar"
    assert recovered_state.get("status") == "collecting"


def test_route_keeps_calendar_sticky_for_pending_replace_existing(monkeypatch):
    fake_calendar_features = types.ModuleType("api.utils.calendar_feature_flags")
    fake_calendar_features.client_can_use_calendar_ai_for_channel = lambda _client_id, _channel: True
    monkeypatch.setitem(sys.modules, "api.utils.calendar_feature_flags", fake_calendar_features)

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())
    monkeypatch.setattr(
        intent_router,
        "get_state",
        lambda _client_id, _session_id: {
            "intent": "calendar",
            "status": "pending_replace_existing",
            "collected": {"scheduled_time": "2026-03-11T09:00:00-06:00"},
        },
    )
    monkeypatch.setattr(intent_router, "detect_intent_to_schedule", lambda _message: False)

    upserts = []
    monkeypatch.setattr(
        intent_router,
        "upsert_state",
        lambda client_id, session_id, state: upserts.append((client_id, session_id, dict(state or {}))),
    )

    route = intent_router.route_message(
        client_id="client-1",
        session_id="session-1",
        message="si",
        channel="whatsapp",
    )

    assert route == "calendar"
    assert upserts == []
