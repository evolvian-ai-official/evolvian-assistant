import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class _DummyRequest:
    def __init__(self):
        self.headers = {"user-agent": "pytest-agent"}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_register_client_consent_inserts_row(monkeypatch):
    from api import register_consent as module

    inserted_rows = []

    class _FakeTable:
        def insert(self, payload):
            inserted_rows.append(payload)
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": "consent_abc"}])

    class _FakeSupabase:
        def table(self, table_name: str):
            assert table_name == "widget_consents"
            return _FakeTable()

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    payload = module.ClientConsentInput(
        client_id="client_1",
        email="Person@Example.com",
        accepted_terms=True,
        accepted_email_marketing=False,
        consent_at=datetime(2026, 2, 19, 20, 0, tzinfo=timezone.utc),
    )

    result = asyncio.run(module.register_client_consent(payload, _DummyRequest()))
    assert result["consent_token"] == "consent_abc"
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["client_id"] == "client_1"
    assert inserted_rows[0]["email"] == "person@example.com"
    assert inserted_rows[0]["accepted_terms"] is True


def test_register_client_consent_requires_email_or_phone(monkeypatch):
    from api import register_consent as module

    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    payload = module.ClientConsentInput(
        client_id="client_1",
        email=None,
        phone=None,
        accepted_terms=True,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(module.register_client_consent(payload, _DummyRequest()))
    assert exc.value.status_code == 422
