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


def test_whatsapp_campaign_interest_handoff_does_not_block_scheduling(monkeypatch):
    fake_calendar_features = types.ModuleType("api.utils.calendar_feature_flags")
    fake_calendar_features.client_can_use_calendar_ai_for_channel = lambda _client_id, _channel: True
    monkeypatch.setitem(sys.modules, "api.utils.calendar_feature_flags", fake_calendar_features)

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())
    monkeypatch.setattr(
        intent_router,
        "_get_active_campaign_interest_handoff",
        lambda *_a, **_k: {"id": "handoff-1", "status": "open"},
    )

    state_store = {}

    def _get_state(client_id, session_id):
        return dict(state_store.get((client_id, session_id), {}))

    def _upsert_state(client_id, session_id, state):
        state_store[(client_id, session_id)] = dict(state or {})

    async def _calendar_handler(client_id, _message, _session_id, channel_name, _lang):
        return f"CALENDAR_OK|{client_id}|{channel_name}"

    def _unexpected_rag(*_args, **_kwargs):
        raise AssertionError("ask_question should not run for scheduling message")

    monkeypatch.setattr(intent_router, "get_state", _get_state)
    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "_calendar_handler", _calendar_handler)
    monkeypatch.setattr(intent_router, "ask_question", _unexpected_rag)
    monkeypatch.setattr(intent_router, "save_history", lambda *_a, **_k: None)

    answer = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id="whatsapp-525512345678",
            message="Quiero agendar",
            channel="whatsapp",
            provider="twilio",
        )
    )

    assert str(answer).startswith("CALENDAR_OK|")
