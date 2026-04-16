from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils import calendar_plan_cleanup as cleanup


class _FakeQuery:
    def __init__(self, db, table_name):
        self._db = db
        self._table_name = table_name
        self._filters = []
        self._payload = None
        self._mode = "select"
        self._limit = None
        self._maybe_single = False

    def select(self, _fields):
        self._mode = "select"
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def maybe_single(self):
        self._maybe_single = True
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
            data = [dict(row) for row in matched]
            if self._limit is not None:
                data = data[: self._limit]
            if self._maybe_single:
                return SimpleNamespace(data=(data[0] if data else None))
            return SimpleNamespace(data=data)

        if self._mode == "update":
            for row in matched:
                row.update(self._payload)
            return SimpleNamespace(data=[dict(row) for row in matched])

        if self._mode == "insert":
            rows.append(dict(self._payload))
            return SimpleNamespace(data=[dict(self._payload)])

        raise AssertionError(f"Unexpected mode: {self._mode}")


class _FakeSupabase:
    def __init__(self, seed):
        self.db = {table: [dict(row) for row in rows] for table, rows in (seed or {}).items()}

    def table(self, table_name):
        return _FakeQuery(self.db, table_name)


def test_disconnect_calendar_features_for_downgraded_plan(monkeypatch):
    client_id = "client-1"
    fake_supabase = _FakeSupabase(
        {
            "plan_features": [
                {"plan_id": "starter", "feature": "calendar_sync", "is_active": True},
            ],
            "calendar_settings": [
                {
                    "client_id": client_id,
                    "show_agenda_in_chat_widget": True,
                    "ai_scheduling_chat_enabled": True,
                    "ai_scheduling_whatsapp_enabled": True,
                }
            ],
            "calendar_integrations": [
                {
                    "client_id": client_id,
                    "is_active": True,
                    "connected_email": "owner@example.com",
                }
            ],
        }
    )

    monkeypatch.setattr(
        cleanup,
        "resolve_effective_plan_id",
        lambda _client_id, *, base_plan_id=None, supabase_client=None: base_plan_id or "free",
    )

    result = cleanup.disconnect_calendar_features_for_plan(
        client_id,
        base_plan_id="starter",
        supabase_client=fake_supabase,
    )

    settings = fake_supabase.db["calendar_settings"][0]
    integration = fake_supabase.db["calendar_integrations"][0]

    assert result["effective_plan_id"] == "starter"
    assert result["settings_updated"] is True
    assert result["google_disconnected"] is True
    assert settings["show_agenda_in_chat_widget"] is False
    assert settings["ai_scheduling_chat_enabled"] is False
    assert settings["ai_scheduling_whatsapp_enabled"] is False
    assert integration["is_active"] is False
    assert integration["connected_email"] is None


def test_disconnect_calendar_features_for_allowed_plan_keeps_existing_connections(monkeypatch):
    client_id = "client-1"
    fake_supabase = _FakeSupabase(
        {
            "plan_features": [
                {"plan_id": "premium", "feature": "calendar_sync", "is_active": True},
                {"plan_id": "premium", "feature": "widget_calendar_booking", "is_active": True},
                {"plan_id": "premium", "feature": "calendar_ai_chat", "is_active": True},
                {"plan_id": "premium", "feature": "calendar_ai_whatsapp", "is_active": True},
                {"plan_id": "premium", "feature": "google_calendar_sync", "is_active": True},
            ],
            "calendar_settings": [
                {
                    "client_id": client_id,
                    "show_agenda_in_chat_widget": True,
                    "ai_scheduling_chat_enabled": True,
                    "ai_scheduling_whatsapp_enabled": True,
                }
            ],
            "calendar_integrations": [
                {
                    "client_id": client_id,
                    "is_active": True,
                    "connected_email": "owner@example.com",
                }
            ],
        }
    )

    monkeypatch.setattr(
        cleanup,
        "resolve_effective_plan_id",
        lambda _client_id, *, base_plan_id=None, supabase_client=None: base_plan_id or "free",
    )

    result = cleanup.disconnect_calendar_features_for_plan(
        client_id,
        base_plan_id="premium",
        supabase_client=fake_supabase,
    )

    settings = fake_supabase.db["calendar_settings"][0]
    integration = fake_supabase.db["calendar_integrations"][0]

    assert result["effective_plan_id"] == "premium"
    assert result["settings_updated"] is False
    assert result["google_disconnected"] is False
    assert settings["show_agenda_in_chat_widget"] is True
    assert settings["ai_scheduling_chat_enabled"] is True
    assert settings["ai_scheduling_whatsapp_enabled"] is True
    assert integration["is_active"] is True
    assert integration["connected_email"] == "owner@example.com"
