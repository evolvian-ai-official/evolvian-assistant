import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import create_checkout_session as checkout_module


class _FakeRequest:
    def __init__(self, payload, headers=None):
        self._payload = dict(payload or {})
        self.headers = dict(headers or {})

    async def json(self):
        return dict(self._payload)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def select(self, _fields):
        return self

    def eq(self, _key, _value):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=self._result)


class _FakeSupabase:
    def __init__(self, result=None):
        self._result = result or {"subscription_id": None}

    def table(self, _table_name):
        return _FakeQuery(self._result)


def test_ensure_success_url_keeps_checkout_placeholder_literal():
    url = "https://app.evolvianai.com/dashboard?tab=plan"
    resolved = checkout_module._ensure_success_url_has_session_id(url)

    assert resolved == (
        "https://app.evolvianai.com/dashboard?tab=plan&session_id={CHECKOUT_SESSION_ID}"
    )


def test_create_checkout_session_omits_empty_customer_email_and_uses_request_origin(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PREMIUM_ID", "price_premium_test")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "http://localhost:4223/dashboard")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "http://localhost:4223/settings")

    monkeypatch.setattr(checkout_module, "authorize_client_request", lambda request, client_id: "user-1")
    monkeypatch.setattr(
        checkout_module,
        "get_client_override_plan_id",
        lambda client_id, supabase_client=None: None,
    )
    monkeypatch.setattr(checkout_module, "supabase", _FakeSupabase())

    captured = {}

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/test_session", id="cs_test_123")

    monkeypatch.setattr(checkout_module.stripe.checkout.Session, "create", _fake_create)

    payload = {
        "client_id": "client-123",
        "plan_id": "premium",
        "email": "   ",
    }
    request = _FakeRequest(payload, headers={"origin": "https://app.evolvianai.com"})

    response = asyncio.run(checkout_module.create_checkout_session(request))

    assert response == {"url": "https://checkout.stripe.com/c/pay/test_session"}
    assert "customer_email" not in captured
    assert captured["client_reference_id"] == "client-123"
    assert captured["success_url"] == (
        "https://app.evolvianai.com/dashboard?session_id={CHECKOUT_SESSION_ID}"
    )
    assert captured["cancel_url"] == "https://app.evolvianai.com/settings"
