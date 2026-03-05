import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.getcwd())


def test_upsert_whatsapp_handoff_reopens_existing_acknowledged_alert(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    state = {
        "conversations": [
            {
                "id": "conv_1",
                "client_id": "client_1",
                "session_id": "whatsapp-5215512345678",
                "status": "human_in_progress",
            }
        ],
        "handoffs": [
            {
                "id": "handoff_1",
                "client_id": "client_1",
                "session_id": "whatsapp-5215512345678",
                "channel": "whatsapp",
                "status": "assigned",
                "created_at": "2026-03-05T10:00:00+00:00",
            }
        ],
        "alerts": [
            {
                "id": "alert_1",
                "client_id": "client_1",
                "source_handoff_request_id": "handoff_1",
                "status": "acknowledged",
                "created_at": "2026-03-05T10:01:00+00:00",
                "resolved_at": "2026-03-05T10:02:00+00:00",
                "title": "Old",
                "body": "Old body",
            }
        ],
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}
            self.in_filters = {}
            self.payload = None
            self._limit = None
            self._maybe_single = False

        def select(self, *_args, **_kwargs):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def in_(self, key, values):
            self.in_filters[key] = set(values)
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, n):
            self._limit = n
            return self

        def maybe_single(self):
            self._maybe_single = True
            return self

        def update(self, payload):
            self.mode = "update"
            self.payload = payload
            return self

        def insert(self, payload):
            self.mode = "insert"
            self.payload = payload
            return self

        def _rows(self):
            if self.table_name == "conversations":
                return state["conversations"]
            if self.table_name == "conversation_handoff_requests":
                return state["handoffs"]
            if self.table_name == "conversation_alerts":
                return state["alerts"]
            return []

        def _match(self, row):
            for k, v in self.filters.items():
                if row.get(k) != v:
                    return False
            for k, values in self.in_filters.items():
                if row.get(k) not in values:
                    return False
            return True

        def execute(self):
            if self.mode == "select":
                rows = [row for row in self._rows() if self._match(row)]
                if self._limit is not None:
                    rows = rows[: self._limit]
                if self._maybe_single:
                    return SimpleNamespace(data=rows[0] if rows else None)
                return SimpleNamespace(data=rows)

            if self.mode == "update":
                updated = []
                for row in self._rows():
                    if self._match(row):
                        row.update(dict(self.payload or {}))
                        updated.append(dict(row))
                return SimpleNamespace(data=updated)

            if self.mode == "insert":
                payload = dict(self.payload or {})
                if not payload.get("id"):
                    payload["id"] = f"{self.table_name}_new"
                if self.table_name == "conversations":
                    state["conversations"].append(payload)
                elif self.table_name == "conversation_handoff_requests":
                    state["handoffs"].append(payload)
                elif self.table_name == "conversation_alerts":
                    state["alerts"].append(payload)
                return SimpleNamespace(data=[payload])

            raise AssertionError(f"Unsupported mode: {self.mode}")

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "_client_has_handoff_feature", lambda _client_id: True)
    monkeypatch.setattr(module, "_extract_phone_from_session", lambda _session_id: "+525512345678")

    result = module._upsert_whatsapp_handoff(
        client_id="client_1",
        session_id="whatsapp-5215512345678",
        user_message="Me interesa",
        ai_message="",
        trigger="campaign_interest_button",
        reason="campaign_interest",
        language="es",
        metadata_origin="marketing_campaign",
    )

    assert result["handoff_id"] == "handoff_1"
    assert result["reused"] is True
    assert result["alert_created"] is True
    assert state["alerts"][0]["status"] == "open"
    assert state["alerts"][0]["resolved_at"] is None
