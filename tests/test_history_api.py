import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeHistoryQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, _fields):
        return self

    def eq(self, _column, _value):
        return self

    def order(self, _column, desc=False):
        assert desc is True
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, table_name):
        assert table_name == "history"
        return _FakeHistoryQuery(self._rows)


def _request() -> Request:
    return Request({"type": "http", "headers": []})


def test_history_hides_system_events_by_default(monkeypatch):
    from api import history_api as module

    rows = [
        {
            "role": "assistant",
            "content": "Outbound policy pre_send: channel=email",
            "created_at": "2026-02-19T20:47:58Z",
            "session_id": "proof_abcd1234",
            "channel": "email",
            "source_type": "compliance_outbound_policy",
            "provider": "internal",
            "status": "allowed_policy",
            "source_id": None,
            "metadata": {"compliance_event": "outbound_policy"},
        },
        {
            "role": "assistant",
            "content": "Respuesta normal del asistente",
            "created_at": "2026-02-19T20:47:57Z",
            "session_id": "session_1",
            "channel": "chat",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
        {
            "role": "assistant",
            "content": "analytics_event payload",
            "created_at": "2026-02-19T20:47:56Z",
            "session_id": "analytics_1",
            "channel": "chat",
            "source_type": "analytics_event",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
    ]

    monkeypatch.setattr(module, "supabase", _FakeSupabase(rows))
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)

    response = module.get_history(
        _request(),
        client_id="client_1",
        session_id=None,
        limit=50,
        include_system_events=False,
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["count"] == 1
    assert payload["history"][0]["session_id"] == "session_1"
    assert payload["history"][0]["content"] == "Respuesta normal del asistente"


def test_history_can_include_system_events_when_requested(monkeypatch):
    from api import history_api as module

    rows = [
        {
            "role": "assistant",
            "content": "Outbound policy post_send: channel=email",
            "created_at": "2026-02-19T20:47:59Z",
            "session_id": "proof_abcd1234",
            "channel": "email",
            "source_type": "compliance_outbound_policy",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": {"compliance_event": "outbound_policy"},
        },
        {
            "role": "assistant",
            "content": "Mensaje normal",
            "created_at": "2026-02-19T20:47:57Z",
            "session_id": "session_1",
            "channel": "chat",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
    ]

    monkeypatch.setattr(module, "supabase", _FakeSupabase(rows))
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)

    response = module.get_history(
        _request(),
        client_id="client_1",
        session_id=None,
        limit=50,
        include_system_events=True,
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["count"] == 2
    assert payload["history"][0]["session_id"] == "proof_abcd1234"
    assert payload["history"][1]["session_id"] == "session_1"


def test_history_insights_fallback_detects_patterns(monkeypatch):
    from api import history_api as module

    rows = [
        {
            "role": "user",
            "content": "Quiero agendar una cita para mañana",
            "created_at": "2026-02-19T20:47:59Z",
            "session_id": "session_1",
            "channel": "widget",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
        {
            "role": "assistant",
            "content": "Claro, te comparto horarios disponibles.",
            "created_at": "2026-02-19T20:48:00Z",
            "session_id": "session_1",
            "channel": "widget",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
        {
            "role": "user",
            "content": "Que precio tiene la consulta?",
            "created_at": "2026-02-19T20:49:01Z",
            "session_id": "session_2",
            "channel": "whatsapp",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
        {
            "role": "user",
            "content": "Que precio tiene la consulta?",
            "created_at": "2026-02-19T20:49:40Z",
            "session_id": "session_3",
            "channel": "whatsapp",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
    ]

    monkeypatch.setattr(module, "supabase", _FakeSupabase(rows))
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(module, "require_client_feature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "openai_chat", lambda *args, **kwargs: "Error: unavailable")

    payload = module.get_history_insights(
        _request(),
        client_id="client_1",
        limit=100,
        include_system_events=False,
        lang="es",
    )

    assert payload["provider"] == "heuristic"
    assert payload["stats"]["conversation_count"] == 3
    assert payload["stats"]["message_count"] == 4
    assert payload["faq"][0]["question"] == "Que precio tiene la consulta?"
    assert payload["faq"][0]["mentions"] == 2
    assert any(topic["topic"] == "Citas y agenda" for topic in payload["top_topics"])
    assert payload["unresolved_sessions"][0]["session_id"] in {"session_2", "session_3"}


def test_history_insights_prefers_ai_json_when_available(monkeypatch):
    from api import history_api as module

    rows = [
        {
            "role": "user",
            "content": "Do you have appointments for tomorrow?",
            "created_at": "2026-02-19T20:47:59Z",
            "session_id": "session_1",
            "channel": "chat",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
        {
            "role": "assistant",
            "content": "Yes, I can help you schedule that.",
            "created_at": "2026-02-19T20:48:00Z",
            "session_id": "session_1",
            "channel": "chat",
            "source_type": "chat",
            "provider": "internal",
            "status": "sent",
            "source_id": None,
            "metadata": None,
        },
    ]

    monkeypatch.setattr(module, "supabase", _FakeSupabase(rows))
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(module, "require_client_feature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "openai_chat",
        lambda *args, **kwargs: json.dumps(
            {
                "summary": "Customers mostly ask about availability and next booking steps.",
                "faq": [
                    {
                        "question": "Do you have appointments for tomorrow?",
                        "mentions": 3,
                        "note": "Availability is the main repeated request.",
                    }
                ],
                "top_topics": [
                    {
                        "topic": "Availability",
                        "mentions": 3,
                        "note": "Customers want quick scheduling confirmation.",
                    }
                ],
                "customer_goals": ["Book an appointment quickly"],
                "friction_points": ["Customers need faster availability answers"],
                "recommendations": ["Publish available time windows earlier in the flow"],
            }
        ),
    )

    payload = module.get_history_insights(
        _request(),
        client_id="client_1",
        limit=50,
        include_system_events=False,
        lang="en",
    )

    assert payload["provider"] == "openai"
    assert payload["summary"] == "Customers mostly ask about availability and next booking steps."
    assert payload["faq"][0]["mentions"] == 3
    assert payload["top_topics"][0]["topic"] == "Availability"
    assert payload["customer_goals"] == ["Book an appointment quickly"]


def test_history_insights_requires_conversation_insights_feature(monkeypatch):
    from api import history_api as module

    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        module,
        "require_client_feature",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=403, detail="premium required")),
    )

    with pytest.raises(HTTPException) as exc:
        module.get_history_insights(
            _request(),
            client_id="client_1",
            limit=50,
            include_system_events=False,
            lang="es",
        )

    assert exc.value.status_code == 403
    assert "premium required" in str(exc.value.detail)
