import asyncio
import types
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import intent_router


def test_campaign_interest_handoff_does_not_hijack_general_transcript(monkeypatch):
    fake_plan_features = types.ModuleType("api.utils.plan_features_logic")
    fake_plan_features.client_has_feature = lambda _client_id, feature_key: feature_key == "calendar_sync"
    monkeypatch.setitem(sys.modules, "api.utils.plan_features_logic", fake_plan_features)

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
            return types.SimpleNamespace(data=row if self._maybe_single else [row])

    class _FakeSupabase:
        def table(self, name):
            if name != "calendar_settings":
                raise AssertionError(f"Unexpected table lookup: {name}")
            return _FakeCalendarSettingsQuery()

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())
    monkeypatch.setattr(
        intent_router,
        "_get_active_campaign_interest_handoff",
        lambda *_a, **_k: {"id": "handoff-1", "status": "open", "reason": "campaign_interest"},
    )

    state_store = {}

    def _get_state(client_id, session_id):
        return dict(state_store.get((client_id, session_id), {}))

    def _upsert_state(client_id, session_id, state):
        state_store[(client_id, session_id)] = dict(state or {})

    async def _calendar_handler(client_id, _message, _session_id, channel_name, _lang):
        return f"CALENDAR_OK|{client_id}|{channel_name}"

    monkeypatch.setattr(intent_router, "get_state", _get_state)
    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "_calendar_handler", _calendar_handler)
    monkeypatch.setattr(intent_router, "save_history", lambda *_a, **_k: None)

    rag_calls = []

    def _route(_client_id, _session_id, message, **_kwargs):
        if "agendar" in str(message).lower():
            return "calendar"
        return "rag"

    monkeypatch.setattr(intent_router, "route_message", _route)
    monkeypatch.setattr(intent_router, "ask_question", lambda *_a, **_k: rag_calls.append(True) or "RAG_OK")

    session_id = "whatsapp-5215511111111"

    msg1 = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id=session_id,
            message="Quiero agendar",
            channel="whatsapp",
            provider="meta",
        )
    )
    assert str(msg1).startswith("CALENDAR_OK|")

    msg2 = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id=session_id,
            message="dame los precios de Evolvian?",
            channel="whatsapp",
            provider="meta",
        )
    )
    assert str(msg2).startswith("RAG_OK")

    msg3 = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id=session_id,
            message="cuales son los precios del plan premium",
            channel="whatsapp",
            provider="meta",
        )
    )
    assert str(msg3).startswith("RAG_OK")

    msg4 = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id=session_id,
            message="hola",
            channel="whatsapp",
            provider="meta",
        )
    )
    assert str(msg4).startswith("RAG_OK")

    msg5 = asyncio.run(
        intent_router.process_user_message(
            client_id="client-1",
            session_id=session_id,
            message="evolvian setup",
            channel="whatsapp",
            provider="meta",
        )
    )
    assert str(msg5).startswith("RAG_OK")

    assert len(rag_calls) == 4
