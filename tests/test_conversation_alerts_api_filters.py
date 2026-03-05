import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.getcwd())


class _DummyRequest:
    headers = {}


def test_conversation_alerts_prospects_aliases_to_open(monkeypatch):
    from api import conversation_alerts_api as module

    state = {
        "alerts": [
            {"id": "a1", "client_id": "client_1", "status": "open", "source_handoff_request_id": None, "created_at": "2026-03-05T00:00:00+00:00"},
            {"id": "a2", "client_id": "client_1", "status": "acknowledged", "source_handoff_request_id": None, "created_at": "2026-03-04T00:00:00+00:00"},
            {"id": "a3", "client_id": "client_1", "status": "resolved", "source_handoff_request_id": None, "created_at": "2026-03-03T00:00:00+00:00"},
        ]
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.filters = {}
            self._limit = None
            self._count_mode = False

        def select(self, *_fields, **kwargs):
            self._count_mode = kwargs.get("count") == "exact"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def in_(self, _key, _values):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, n):
            self._limit = n
            return self

        def execute(self):
            if self.table_name != "conversation_alerts":
                return SimpleNamespace(data=[])

            rows = [
                row
                for row in state["alerts"]
                if all(row.get(k) == v for k, v in self.filters.items())
            ]
            if self._count_mode:
                return SimpleNamespace(data=[], count=len(rows))

            if self._limit is not None:
                rows = rows[: self._limit]
            return SimpleNamespace(data=rows)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "authorize_client_request", lambda *_args, **_kwargs: "user_1")
    monkeypatch.setattr(module, "require_client_feature", lambda *_args, **_kwargs: None)

    result = module.list_conversation_alerts(
        _DummyRequest(),
        client_id="client_1",
        status="prospects",
        limit=50,
    )

    assert result["status_filter"] == "open"
    assert len(result["items"]) == 1
    assert result["items"][0]["status"] == "open"
    assert result["counts"]["open"] == 1
