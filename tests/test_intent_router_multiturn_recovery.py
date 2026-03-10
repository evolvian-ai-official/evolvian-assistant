import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import intent_router


FOLLOWUPS = [
    "mañana a las 9:00",
    "martes 10:30",
    "mi nombre es QA Usuario",
    "mi correo es qa.user@example.com",
    "confirmar",
    "el primer horario",
]


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


@pytest.mark.parametrize("channel", ["chat", "whatsapp"])
@pytest.mark.parametrize("followup_message", FOLLOWUPS)
def test_multiturn_followups_stay_in_calendar_after_state_loss(monkeypatch, channel, followup_message):
    fake_plan_features = types.ModuleType("api.utils.plan_features_logic")
    fake_plan_features.client_has_feature = lambda _client_id, feature_key: feature_key == "calendar_sync"
    monkeypatch.setitem(sys.modules, "api.utils.plan_features_logic", fake_plan_features)

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())

    state_store: dict[tuple[str, str], dict] = {}
    history_events: list[dict] = []

    def _get_state(client_id, session_id):
        return dict(state_store.get((client_id, session_id), {}))

    def _upsert_state(client_id, session_id, state):
        state_store[(client_id, session_id)] = dict(state or {})

    def _save_history(client_id, session_id, role, content, **kwargs):
        history_events.append(
            {
                "client_id": client_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "source_type": kwargs.get("source_type"),
                "channel": kwargs.get("channel"),
            }
        )

    def _has_recent_appointment_history(client_id, session_id, _channel, max_age_minutes=120):  # noqa: ARG001
        return any(
            evt.get("client_id") == client_id
            and evt.get("session_id") == session_id
            and evt.get("source_type") == "appointment"
            for evt in history_events
        )

    async def _calendar_handler(client_id, message, _session_id, channel_name, _lang):
        return f"CALENDAR_OK|{client_id}|{channel_name}|{message}"

    def _unexpected_rag(*_args, **_kwargs):
        raise AssertionError("ask_question should not run during recovered calendar follow-up")

    monkeypatch.setattr(intent_router, "get_state", _get_state)
    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "save_history", _save_history)
    monkeypatch.setattr(intent_router, "_has_recent_appointment_history", _has_recent_appointment_history)
    monkeypatch.setattr(intent_router, "_calendar_handler", _calendar_handler)
    monkeypatch.setattr(intent_router, "ask_question", _unexpected_rag)

    client_id = "client-1"
    session_id = "session-1"

    first = asyncio.run(
        intent_router.process_user_message(
            client_id=client_id,
            session_id=session_id,
            message="Quiero agendar una cita",
            channel=channel,
            provider="widget" if channel == "chat" else "twilio",
        )
    )
    assert str(first).startswith("CALENDAR_OK|")

    # Simulate intermittent state loss between turns.
    state_store.clear()

    second = asyncio.run(
        intent_router.process_user_message(
            client_id=client_id,
            session_id=session_id,
            message=followup_message,
            channel=channel,
            provider="widget" if channel == "chat" else "twilio",
        )
    )
    assert str(second).startswith("CALENDAR_OK|")
