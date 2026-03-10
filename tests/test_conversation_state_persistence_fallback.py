import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import calendar_intent_handler
from api.modules.assistant_rag import intent_router


_CONSTRAINT_ERR = "there is no unique or exclusion constraint matching the ON CONFLICT specification"


class _FallbackConversationStateQuery:
    def __init__(self, store: dict, actions: list[str], table_name: str):
        self.store = store
        self.actions = actions
        self.table_name = table_name
        self._action = None
        self._payload = None
        self._filters = {}

    def select(self, _fields):
        self._action = "select"
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def limit(self, _n):
        return self

    def upsert(self, payload, on_conflict=None):  # noqa: ARG002
        self._action = "upsert"
        self._payload = payload
        return self

    def update(self, payload):
        self._action = "update"
        self._payload = payload
        return self

    def insert(self, payload):
        self._action = "insert"
        self._payload = payload
        return self

    def execute(self):
        if self.table_name != "conversation_state":
            raise AssertionError(f"Unexpected table: {self.table_name}")

        self.actions.append(self._action or "execute")

        if self._action == "upsert":
            raise Exception({"code": "42P10", "message": _CONSTRAINT_ERR})

        if self._action == "select":
            key = (self._filters.get("client_id"), self._filters.get("session_id"))
            row = self.store.get(key)
            return SimpleNamespace(data=[row] if row else [])

        if self._action == "update":
            key = (self._filters.get("client_id"), self._filters.get("session_id"))
            if key in self.store:
                self.store[key] = {
                    "client_id": key[0],
                    "session_id": key[1],
                    "state": (self._payload or {}).get("state") or {},
                }
                return SimpleNamespace(data=[self.store[key]])
            return SimpleNamespace(data=[])

        if self._action == "insert":
            payload = dict(self._payload or {})
            key = (payload.get("client_id"), payload.get("session_id"))
            self.store[key] = {
                "client_id": key[0],
                "session_id": key[1],
                "state": payload.get("state") or {},
            }
            return SimpleNamespace(data=[self.store[key]])

        raise AssertionError(f"Unexpected action: {self._action}")


class _FakeSupabase:
    def __init__(self, initial_rows: dict | None = None):
        self.store = dict(initial_rows or {})
        self.actions: list[str] = []

    def table(self, name: str):
        return _FallbackConversationStateQuery(self.store, self.actions, name)


def test_intent_router_upsert_state_fallback_updates_existing_row(monkeypatch):
    key = ("client-1", "session-1")
    fake_supabase = _FakeSupabase(
        {
            key: {
                "client_id": key[0],
                "session_id": key[1],
                "state": {"intent": "calendar", "status": "collecting"},
            }
        }
    )
    monkeypatch.setattr(intent_router, "supabase", fake_supabase)

    intent_router.upsert_state(key[0], key[1], {"intent": "calendar", "status": "pending_confirmation"})

    assert fake_supabase.store[key]["state"]["status"] == "pending_confirmation"
    assert "upsert" in fake_supabase.actions
    assert "select" in fake_supabase.actions
    assert "update" in fake_supabase.actions
    assert "insert" not in fake_supabase.actions


def test_intent_router_upsert_state_fallback_inserts_missing_row(monkeypatch):
    key = ("client-2", "session-2")
    fake_supabase = _FakeSupabase()
    monkeypatch.setattr(intent_router, "supabase", fake_supabase)

    intent_router.upsert_state(key[0], key[1], {"intent": "calendar", "status": "collecting"})

    assert key in fake_supabase.store
    assert fake_supabase.store[key]["state"]["intent"] == "calendar"
    assert "select" in fake_supabase.actions
    assert "insert" in fake_supabase.actions


def test_calendar_state_persist_fallback_handles_42p10(monkeypatch):
    key = ("client-3", "session-3")
    fake_supabase = _FakeSupabase()
    monkeypatch.setattr(calendar_intent_handler, "supabase", fake_supabase)

    ok = calendar_intent_handler._persist_conversation_state(
        key[0],
        key[1],
        {"intent": "calendar", "status": "collecting", "collected": {"user_name": "Aldo"}},
    )

    assert ok is True
    assert key in fake_supabase.store
    assert fake_supabase.store[key]["state"]["collected"]["user_name"] == "Aldo"
    assert "select" in fake_supabase.actions
    assert "insert" in fake_supabase.actions
