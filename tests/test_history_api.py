import json
from types import SimpleNamespace

from starlette.requests import Request


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
