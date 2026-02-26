import asyncio
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


sys.path.insert(0, os.getcwd())


class _DummyRequest:
    def __init__(self):
        self.headers = {"user-agent": "pytest-agent"}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_widget_handoff_request_creates_records(monkeypatch):
    from api import widget_handoff_api as module

    inserted = {
        "widget_consents": [],
        "conversations": [],
        "conversation_handoff_requests": [],
        "conversation_alerts": [],
    }

    class _FakeQuery:
        def __init__(self, table_name: str, mode: str = "select"):
            self.table_name = table_name
            self.mode = mode
            self.payload = None
            self.filters = {}

        def select(self, _fields: str):
            self.mode = "select"
            return self

        def eq(self, key: str, value):
            self.filters[key] = value
            return self

        def limit(self, _n: int):
            return self

        def maybe_single(self):
            self.mode = "maybe_single"
            return self

        def insert(self, payload):
            self.mode = "insert"
            self.payload = payload
            return self

        def update(self, payload):
            self.mode = "update"
            self.payload = payload
            return self

        def execute(self):
            if self.table_name == "clients":
                return SimpleNamespace(data=[{"id": "client_abc"}])

            if self.mode == "maybe_single" and self.table_name == "conversations":
                return SimpleNamespace(data=None)

            if self.mode == "insert":
                inserted[self.table_name].append(self.payload)
                generated_id = {
                    "widget_consents": "consent_1",
                    "conversations": "conv_1",
                    "conversation_handoff_requests": "handoff_1",
                    "conversation_alerts": "alert_1",
                }.get(self.table_name, "row_1")
                return SimpleNamespace(data=[{"id": generated_id}])

            if self.mode == "update":
                return SimpleNamespace(data=[{"id": "conv_1"}])

            return SimpleNamespace(data=[])

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    payload = module.WidgetHandoffRequestInput(
        public_client_id="public_123",
        session_id="session_123",
        user_name="Ada",
        email="Ada@Example.com",
        phone=None,
        accepted_terms=True,
        accepted_email_marketing=True,
        trigger="manual_request",
        reason="user_requested_human",
        last_user_message="Necesito hablar con alguien",
        language="es",
    )

    result = asyncio.run(module.create_widget_handoff_request(payload, _DummyRequest()))

    assert result["success"] is True
    assert result["handoff_request_id"] == "handoff_1"
    assert result["consent_token"] == "consent_1"
    assert result["alert_created"] is True
    assert inserted["widget_consents"][0]["email"] == "ada@example.com"
    assert inserted["conversation_handoff_requests"][0]["contact_name"] == "Ada"
    assert inserted["conversation_alerts"][0]["alert_type"] == "human_intervention"


def test_widget_handoff_request_requires_terms_and_contact(monkeypatch):
    from api import widget_handoff_api as module

    class _FakeSupabase:
        def table(self, _table_name: str):
            class _Q:
                def select(self, _fields):
                    return self

                def eq(self, _k, _v):
                    return self

                def limit(self, _n):
                    return self

                def execute(self):
                    return SimpleNamespace(data=[{"id": "client_abc"}])

            return _Q()

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    payload = module.WidgetHandoffRequestInput(
        public_client_id="public_123",
        session_id="session_123",
        user_name="",
        email=None,
        phone=None,
        accepted_terms=False,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(module.create_widget_handoff_request(payload, _DummyRequest()))
    assert exc.value.status_code == 422
