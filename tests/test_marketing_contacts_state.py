from types import SimpleNamespace

from api.marketing_contacts_state import upsert_marketing_contact_state


def test_latest_consent_overwrites_older_opt_in_state():
    state = {"rows": []}

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}
            self.payload = None

        def select(self, _fields):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
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
            if self.table_name != "marketing_contacts":
                raise AssertionError(self.table_name)

            if self.mode == "select":
                rows = state["rows"]
                for key, value in self.filters.items():
                    rows = [row for row in rows if row.get(key) == value]
                return SimpleNamespace(data=rows[:1])

            if self.mode == "insert":
                payload = dict(self.payload or {})
                payload["id"] = f"contact_{len(state['rows']) + 1}"
                state["rows"].append(payload)
                return SimpleNamespace(data=[payload])

            if self.mode == "update":
                target_id = self.filters.get("id")
                for row in state["rows"]:
                    if row.get("id") == target_id:
                        row.update(dict(self.payload or {}))
                        return SimpleNamespace(data=[row])
                raise AssertionError(f"Missing row id={target_id}")

            raise AssertionError(self.mode)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    supabase = _FakeSupabase()

    assert upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_1",
        email="test@example.com",
        email_opt_in=True,
        seen_at="2026-03-17T10:00:00+00:00",
    )

    assert upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_1",
        email="test@example.com",
        email_opt_in=False,
        seen_at="2026-03-18T10:00:00+00:00",
    )

    assert state["rows"][0]["email_opt_in"] is False
    assert state["rows"][0]["last_seen_at"] == "2026-03-18T10:00:00+00:00"


def test_older_consent_does_not_overwrite_newer_marketing_state():
    state = {"rows": []}

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.mode = "select"
            self.filters = {}
            self.payload = None

        def select(self, _fields):
            self.mode = "select"
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
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
            if self.table_name != "marketing_contacts":
                raise AssertionError(self.table_name)

            if self.mode == "select":
                rows = state["rows"]
                for key, value in self.filters.items():
                    rows = [row for row in rows if row.get(key) == value]
                return SimpleNamespace(data=rows[:1])

            if self.mode == "insert":
                payload = dict(self.payload or {})
                payload["id"] = f"contact_{len(state['rows']) + 1}"
                state["rows"].append(payload)
                return SimpleNamespace(data=[payload])

            if self.mode == "update":
                target_id = self.filters.get("id")
                for row in state["rows"]:
                    if row.get("id") == target_id:
                        row.update(dict(self.payload or {}))
                        return SimpleNamespace(data=[row])
                raise AssertionError(f"Missing row id={target_id}")

            raise AssertionError(self.mode)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    supabase = _FakeSupabase()

    assert upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_1",
        email="test@example.com",
        email_opt_in=False,
        email_unsubscribed=True,
        seen_at="2026-03-18T10:00:00+00:00",
    )

    assert upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_1",
        email="test@example.com",
        email_opt_in=True,
        email_unsubscribed=False,
        seen_at="2026-03-17T10:00:00+00:00",
    )

    assert state["rows"][0]["email_opt_in"] is False
    assert state["rows"][0]["email_unsubscribed"] is True
    assert state["rows"][0]["last_seen_at"] == "2026-03-18T10:00:00+00:00"
