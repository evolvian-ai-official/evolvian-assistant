import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())

from api import marketing_campaigns as module


class _FakeQuery:
    def __init__(self, table_name: str, state: dict):
        self.table_name = table_name
        self.state = state
        self.filters = []

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, tuple(values)))
        return self

    def order(self, _key, desc=False):
        return self

    def limit(self, _n):
        return self

    def execute(self):
        rows = list(self.state.get(self.table_name, []))
        for op, key, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(key) == value]
            elif op == "in":
                rows = [row for row in rows if row.get(key) in value]
            else:
                raise AssertionError(op)
        return SimpleNamespace(data=rows)


class _FakeSupabase:
    def __init__(self, state: dict):
        self.state = state

    def table(self, table_name: str):
        return _FakeQuery(table_name, self.state)


def test_get_marketing_history_for_recipient_includes_response_status(monkeypatch):
    state = {
        "marketing_campaign_recipients": [
            {
                "client_id": "client_1",
                "campaign_id": "campaign_1",
                "recipient_key": "email:test@example.com",
                "send_status": "sent",
                "provider_message_id": "provider_1",
                "policy_proof_id": "proof_1",
                "send_error": None,
                "sent_at": "2026-03-18T10:00:00+00:00",
                "updated_at": "2026-03-18T10:00:00+00:00",
                "segment": "clients",
            }
        ],
        "marketing_campaigns": [
            {
                "id": "campaign_1",
                "client_id": "client_1",
                "name": "Promo marzo",
                "channel": "email",
                "status": "sent",
                "created_at": "2026-03-18T09:00:00+00:00",
                "last_sent_at": "2026-03-18T10:00:00+00:00",
            }
        ],
        "marketing_campaign_events": [
            {
                "client_id": "client_1",
                "campaign_id": "campaign_1",
                "recipient_key": "email:test@example.com",
                "event_type": "interest_yes",
                "created_at": "2026-03-18T10:05:00+00:00",
            }
        ],
    }

    monkeypatch.setattr(module, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(module, "authorize_client_request", lambda *_args, **_kwargs: "user_1")
    monkeypatch.setattr(module, "_ensure_premium_access", lambda *_args, **_kwargs: None)

    result = module.get_marketing_history_for_recipient(
        request=SimpleNamespace(),
        client_id="client_1",
        recipient_key="email:test@example.com",
    )

    assert result["items"][0]["send_status"] == "sent"
    assert result["items"][0]["response_status"] == "interested"
    assert result["items"][0]["response_at"] == "2026-03-18T10:05:00+00:00"


def test_load_contacts_audience_applies_marketing_contact_state(monkeypatch):
    state = {
        "appointment_clients": [
            {
                "client_id": "client_1",
                "user_name": "Holistica Condesa Spa",
                "user_email": "condesa.spa@gmail.com",
                "user_phone": None,
                "updated_at": "2026-03-18T17:05:00+00:00",
                "created_at": "2026-03-18T17:00:00+00:00",
            }
        ],
        "appointments": [],
        "widget_consents": [],
        "conversation_handoff_requests": [],
        "public_privacy_requests": [],
        "client_settings": [{"client_id": "client_1", "consent_renewal_days": 90}],
        "client_profile": [{"client_id": "client_1", "country": "Mexico"}],
        "marketing_contacts": [
            {
                "client_id": "client_1",
                "normalized_email": "condesa.spa@gmail.com",
                "normalized_phone": None,
                "interest_status": "interested",
                "email_unsubscribed": False,
                "whatsapp_unsubscribed": False,
                "last_seen_at": "2026-03-18T17:06:00+00:00",
            }
        ],
    }

    monkeypatch.setattr(module, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(module, "backfill_default_marketing_consents_for_contacts", lambda **_kwargs: None)
    module._get_client_country_code.cache_clear()

    result = module._load_contacts_audience("client_1")

    assert len(result) == 1
    assert result[0]["recipient_key"] == "email:condesa.spa@gmail.com"
    assert result[0]["interest_status"] == "interested"
    assert result[0]["email_unsubscribed"] is False
    assert result[0]["marketing_state_last_seen_at"] == "2026-03-18T17:06:00+00:00"
