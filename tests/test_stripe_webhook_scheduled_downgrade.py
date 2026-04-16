import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import stripe_webhook as stripe_webhook_module


class _FakeRequest:
    def __init__(self):
        self.headers = {"stripe-signature": "test"}

    async def body(self):
        return b"{}"


class _FakeQuery:
    def __init__(self, db, table_name):
        self._db = db
        self._table_name = table_name
        self._filters = []
        self._payload = None
        self._mode = "select"

    def select(self, _fields):
        self._mode = "select"
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def update(self, payload):
        self._mode = "update"
        self._payload = dict(payload or {})
        return self

    def insert(self, payload):
        self._mode = "insert"
        self._payload = dict(payload or {})
        return self

    def execute(self):
        rows = self._db.setdefault(self._table_name, [])

        def _matches(row):
            return all(row.get(key) == value for key, value in self._filters)

        matched = [row for row in rows if _matches(row)]

        if self._mode == "select":
            return SimpleNamespace(data=[dict(row) for row in matched])

        if self._mode == "update":
            for row in matched:
                row.update(self._payload)
            return SimpleNamespace(data=[dict(row) for row in matched])

        if self._mode == "insert":
            rows.append(dict(self._payload))
            return SimpleNamespace(data=[dict(self._payload)])

        raise AssertionError(f"Unsupported mode: {self._mode}")


class _FakeSupabase:
    def __init__(self, seed):
        self.db = {table: [dict(row) for row in rows] for table, rows in seed.items()}

    def table(self, table_name):
        return _FakeQuery(self.db, table_name)


def test_subscription_deleted_materializes_scheduled_paid_downgrade(monkeypatch):
    client_id = "client-1"
    fake_supabase = _FakeSupabase(
        {
            "client_settings": [
                {
                    "client_id": client_id,
                    "plan_id": "premium",
                    "subscription_id": "sub_old",
                    "scheduled_plan_id": "starter",
                    "pending_deleted_subscription_id": None,
                    "upgrade_in_progress": False,
                }
            ]
        }
    )

    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_old",
                "status": "canceled",
                "customer": "cus_123",
                "default_payment_method": "pm_sub_default",
            }
        },
    }

    monkeypatch.setattr(
        stripe_webhook_module.stripe.Webhook,
        "construct_event",
        lambda payload, sig_header, secret: event,
    )
    async def _fake_get_client_id_by_subscription_id(_subscription_id):
        return client_id

    monkeypatch.setattr(
        stripe_webhook_module,
        "get_client_id_by_subscription_id",
        _fake_get_client_id_by_subscription_id,
    )
    monkeypatch.setattr(
        stripe_webhook_module.stripe.Subscription,
        "list",
        lambda customer, status, limit=1: SimpleNamespace(data=[]),
    )
    monkeypatch.setattr(
        stripe_webhook_module.stripe.Customer,
        "retrieve",
        lambda _customer_id: {"invoice_settings": {"default_payment_method": "pm_customer_default"}},
    )
    monkeypatch.setattr(
        stripe_webhook_module,
        "create_subscription_for_customer",
        lambda customer_id, plan_id, default_payment_method=None, metadata=None: {
            "id": "sub_new",
            "current_period_start": 1_700_000_000,
            "current_period_end": 1_700_086_400,
            "customer": customer_id,
            "plan_id": plan_id,
            "default_payment_method": default_payment_method,
            "metadata": metadata or {},
        },
    )

    cleanup_calls = []
    monkeypatch.setattr(
        stripe_webhook_module,
        "disconnect_calendar_features_for_plan",
        lambda client_id, base_plan_id=None, supabase_client=None: cleanup_calls.append(
            {
                "client_id": client_id,
                "base_plan_id": base_plan_id,
            }
        ),
    )
    monkeypatch.setattr(stripe_webhook_module, "supabase", fake_supabase)

    response = asyncio.run(stripe_webhook_module.stripe_webhook(_FakeRequest()))

    assert response.status_code == 200
    settings = fake_supabase.db["client_settings"][0]
    assert settings["plan_id"] == "starter"
    assert settings["subscription_id"] == "sub_new"
    assert settings["scheduled_plan_id"] is None
    assert settings["cancellation_requested_at"] is None
    assert cleanup_calls == [{"client_id": client_id, "base_plan_id": "starter"}]


def test_subscription_deleted_logs_recovery_and_falls_back_to_free_when_paid_downgrade_creation_fails(monkeypatch):
    client_id = "client-1"
    fake_supabase = _FakeSupabase(
        {
            "client_settings": [
                {
                    "client_id": client_id,
                    "plan_id": "premium",
                    "subscription_id": "sub_old",
                    "scheduled_plan_id": "starter",
                    "pending_deleted_subscription_id": None,
                    "upgrade_in_progress": False,
                }
            ],
            "history": [],
        }
    )

    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_old",
                "status": "canceled",
                "customer": "cus_123",
                "default_payment_method": "pm_sub_default",
            }
        },
    }

    monkeypatch.setattr(
        stripe_webhook_module.stripe.Webhook,
        "construct_event",
        lambda payload, sig_header, secret: event,
    )

    async def _fake_get_client_id_by_subscription_id(_subscription_id):
        return client_id

    monkeypatch.setattr(
        stripe_webhook_module,
        "get_client_id_by_subscription_id",
        _fake_get_client_id_by_subscription_id,
    )
    monkeypatch.setattr(
        stripe_webhook_module.stripe.Subscription,
        "list",
        lambda customer, status, limit=1: SimpleNamespace(data=[]),
    )
    monkeypatch.setattr(
        stripe_webhook_module.stripe.Customer,
        "retrieve",
        lambda _customer_id: {"invoice_settings": {"default_payment_method": "pm_customer_default"}},
    )

    def _raise_subscription_creation_failure(*_args, **_kwargs):
        raise RuntimeError("pm_missing")

    monkeypatch.setattr(
        stripe_webhook_module,
        "create_subscription_for_customer",
        _raise_subscription_creation_failure,
    )

    cleanup_calls = []
    monkeypatch.setattr(
        stripe_webhook_module,
        "disconnect_calendar_features_for_plan",
        lambda client_id, base_plan_id=None, supabase_client=None: cleanup_calls.append(
            {
                "client_id": client_id,
                "base_plan_id": base_plan_id,
            }
        ),
    )
    monkeypatch.setattr(stripe_webhook_module, "supabase", fake_supabase)

    response = asyncio.run(stripe_webhook_module.stripe_webhook(_FakeRequest()))

    assert response.status_code == 200
    settings = fake_supabase.db["client_settings"][0]
    history = fake_supabase.db["history"]

    assert settings["plan_id"] == "free"
    assert settings["subscription_id"] is None
    assert settings["scheduled_plan_id"] == "starter"
    assert settings["cancellation_requested_at"] is None
    assert cleanup_calls == [{"client_id": client_id, "base_plan_id": "free"}]
    assert len(history) == 1
    assert history[0]["content"] == "scheduled_downgrade_recovery_needed"
    assert history[0]["source_type"] == "billing_alert"
    assert history[0]["metadata"]["target_plan_id"] == "starter"
