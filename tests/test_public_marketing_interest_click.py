import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.getcwd())


class _DummyRequest:
    headers = {}


def test_marketing_interest_click_redirect_logs_event_and_handoff(monkeypatch):
    from api.public import marketing as module

    state = {
        "marketing_campaigns": [
            {
                "id": "campaign_12345678",
                "client_id": "client_1",
                "name": "Promo Spring",
                "channel": "whatsapp",
                "cta_url": "https://example.com/landing",
                "is_active": True,
            }
        ],
        "marketing_campaign_recipients": [
            {
                "campaign_id": "campaign_12345678",
                "recipient_key": "phone:+525512345678",
                "recipient_name": "Ada",
                "email": "ada@example.com",
                "phone": "+52 55 1234 5678",
            }
        ],
        "marketing_campaign_events": [],
    }
    handoff_calls = []

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}
            self.payload = None
            self._limit = None

        def select(self, _fields):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, n):
            self._limit = n
            return self

        def insert(self, payload):
            self.mode = "insert"
            self.payload = payload
            return self

        def execute(self):
            if self.table_name == "marketing_campaigns" and self.mode == "select":
                rows = [
                    row
                    for row in state["marketing_campaigns"]
                    if all(row.get(k) == v for k, v in self.filters.items())
                ]
                if self._limit is not None:
                    rows = rows[: self._limit]
                return SimpleNamespace(data=rows)

            if self.table_name == "marketing_campaign_recipients" and self.mode == "select":
                rows = [
                    row
                    for row in state["marketing_campaign_recipients"]
                    if all(row.get(k) == v for k, v in self.filters.items())
                ]
                if self._limit is not None:
                    rows = rows[: self._limit]
                return SimpleNamespace(data=rows)

            if self.table_name == "marketing_campaign_events" and self.mode == "insert":
                state["marketing_campaign_events"].append(dict(self.payload or {}))
                return SimpleNamespace(data=[self.payload])

            raise AssertionError(f"Unhandled query: {self.table_name} / {self.mode}")

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "1.2.3.4")
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_upsert_campaign_interest_handoff",
        lambda **kwargs: handoff_calls.append(kwargs) or "handoff_1",
    )

    response = module.marketing_interest_click(
        _DummyRequest(),
        campaign_id="campaign_12345678",
        recipient_key="phone%3A%2B525512345678",
        channel="whatsapp",
    )

    assert response.status_code == 302
    assert response.headers.get("location") == "https://example.com/landing"
    assert len(handoff_calls) == 1
    assert handoff_calls[0]["campaign_id"] == "campaign_12345678"
    assert handoff_calls[0]["channel"] == "whatsapp"
    assert handoff_calls[0]["recipient_key"] == "phone:+525512345678"

    assert len(state["marketing_campaign_events"]) == 1
    event = state["marketing_campaign_events"][0]
    assert event["event_type"] == "interest"
    assert event["campaign_id"] == "campaign_12345678"
    assert event["metadata"]["handoff_id"] == "handoff_1"


def test_marketing_interest_click_without_cta_returns_thanks_html(monkeypatch):
    from api.public import marketing as module

    state = {
        "marketing_campaigns": [
            {
                "id": "campaign_99999999",
                "client_id": "client_1",
                "name": "No CTA Campaign",
                "channel": "email",
                "cta_url": "",
                "is_active": True,
            }
        ]
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}

        def select(self, _fields):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
            return self

        def execute(self):
            if self.table_name == "marketing_campaigns" and self.mode == "select":
                rows = [
                    row
                    for row in state["marketing_campaigns"]
                    if all(row.get(k) == v for k, v in self.filters.items())
                ]
                return SimpleNamespace(data=rows)
            raise AssertionError(f"Unhandled query: {self.table_name} / {self.mode}")

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "1.2.3.4")
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)

    response = module.marketing_interest_click(
        _DummyRequest(),
        campaign_id="campaign_99999999",
        recipient_key=None,
        channel=None,
    )

    assert response.status_code == 200
    assert "Thanks for your interest" in response.body.decode("utf-8")


def test_normalize_recipient_key_recovers_phone_plus():
    from api.public import marketing as module

    assert module._normalize_recipient_key("phone: 525512345678") == "phone:+525512345678"
    assert module._normalize_recipient_key("phone%3A%2B525512345678") == "phone:+525512345678"
