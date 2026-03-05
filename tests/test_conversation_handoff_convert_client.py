import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.getcwd())


class _DummyRequest:
    headers = {}


def test_convert_prospect_to_client_creates_directory_contact(monkeypatch):
    from api import conversation_handoffs_api as module

    state = {
        "handoff": {
            "id": "handoff_1",
            "client_id": "client_1",
            "conversation_id": "conv_1",
            "status": "open",
            "trigger": "campaign_interest_button",
            "reason": "campaign_interest",
            "contact_name": "Ada Lovelace",
            "contact_email": "Ada@Example.com",
            "contact_phone": "+52 55 1234 5678",
            "metadata": {},
        },
        "appointment_clients": [],
        "updated_handoff": None,
    }

    class _FakeQuery:
        def __init__(self, table_name):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}
            self.payload = None
            self._maybe_single = False

        def select(self, _fields):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def in_(self, _key, _values):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, _n):
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

        def execute(self):
            if self.table_name == "conversation_handoff_requests":
                if self.mode == "select":
                    if self._maybe_single:
                        if (
                            self.filters.get("id") == state["handoff"]["id"]
                            and self.filters.get("client_id") == state["handoff"]["client_id"]
                        ):
                            return SimpleNamespace(data=state["handoff"])
                        return SimpleNamespace(data=None)
                    return SimpleNamespace(data=[state["handoff"]])

                if self.mode == "update":
                    updated = dict(state["handoff"])
                    updated.update(self.payload or {})
                    state["handoff"] = updated
                    state["updated_handoff"] = updated
                    return SimpleNamespace(data=[updated])

            if self.table_name == "appointment_clients":
                if self.mode == "select":
                    email = self.filters.get("normalized_email")
                    phone = self.filters.get("normalized_phone")
                    for row in state["appointment_clients"]:
                        if email and row.get("normalized_email") == email:
                            return SimpleNamespace(data=[row])
                        if phone and row.get("normalized_phone") == phone:
                            return SimpleNamespace(data=[row])
                    return SimpleNamespace(data=[])

                if self.mode == "insert":
                    row = dict(self.payload or {})
                    row["id"] = "appt_client_1"
                    state["appointment_clients"].append(row)
                    return SimpleNamespace(data=[row])

                if self.mode == "update":
                    row = dict(state["appointment_clients"][0])
                    row.update(self.payload or {})
                    state["appointment_clients"][0] = row
                    return SimpleNamespace(data=[row])

            if self.table_name == "conversations":
                if self.mode == "update":
                    return SimpleNamespace(data=[{"id": self.filters.get("id")}])
                return SimpleNamespace(data=[])

            return SimpleNamespace(data=[])

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "authorize_client_request", lambda *_args, **_kwargs: "user_1")
    monkeypatch.setattr(module, "require_client_feature", lambda *_args, **_kwargs: None)

    payload = module.ConvertProspectToClientInput(client_id="client_1")
    result = module.convert_prospect_to_client("handoff_1", payload, _DummyRequest())

    assert result["success"] is True
    assert result["appointment_client"]["id"] == "appt_client_1"
    assert result["appointment_client"]["user_email"] == "ada@example.com"
    assert result["appointment_client"]["normalized_phone"] == "+525512345678"
    metadata = (result.get("handoff") or {}).get("metadata") or {}
    assert metadata.get("converted_to_client") is True
    assert metadata.get("lifecycle_stage") == "client"
