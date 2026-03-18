from types import SimpleNamespace

from api import marketing_contacts_state as module

upsert_marketing_contact_state = module.upsert_marketing_contact_state


class _FakeQuery:
    def __init__(self, table_name: str, state: dict):
        self.table_name = table_name
        self.state = state
        self.mode = "select"
        self.filters = []
        self.payload = None

    def select(self, _fields):
        self.mode = "select"
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, tuple(values)))
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
        if self.table_name not in {"marketing_contacts", "client_profile"}:
            raise AssertionError(self.table_name)

        if self.mode == "select":
            if self.table_name == "marketing_contacts":
                rows = self.state["rows"]
            else:
                rows = self.state.get("client_profiles", [])
            for op, key, value in self.filters:
                if op == "eq":
                    rows = [row for row in rows if row.get(key) == value]
                elif op == "in":
                    rows = [row for row in rows if row.get(key) in value]
                else:
                    raise AssertionError(op)
            return SimpleNamespace(data=rows[:1])

        if self.mode == "insert":
            payload = dict(self.payload or {})
            payload["id"] = f"contact_{len(self.state['rows']) + 1}"
            self.state["rows"].append(payload)
            return SimpleNamespace(data=[payload])

        if self.mode == "update":
            target_id = None
            for op, key, value in self.filters:
                if op == "eq" and key == "id":
                    target_id = value
                    break
            for row in self.state["rows"]:
                if row.get("id") == target_id:
                    row.update(dict(self.payload or {}))
                    return SimpleNamespace(data=[row])
            raise AssertionError(f"Missing row id={target_id}")

        raise AssertionError(self.mode)


class _FakeSupabase:
    def __init__(self, state: dict):
        self.state = state

    def table(self, table_name: str):
        return _FakeQuery(table_name, self.state)


def test_latest_consent_overwrites_older_opt_in_state():
    state = {"rows": [], "client_profiles": [{"client_id": "client_1", "country": "Mexico"}]}
    module._resolve_client_country_code.cache_clear()
    module.supabase = _FakeSupabase(state)
    supabase = _FakeSupabase(state)

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
    state = {"rows": [], "client_profiles": [{"client_id": "client_1", "country": "Mexico"}]}
    module._resolve_client_country_code.cache_clear()
    module.supabase = _FakeSupabase(state)
    supabase = _FakeSupabase(state)

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


def test_legacy_local_phone_row_is_upgraded_in_place():
    state = {
        "rows": [
            {
                "id": "contact_1",
                "client_id": "client_1",
                "name": "Aldo",
                "email": "aldo@example.com",
                "normalized_email": "aldo@example.com",
                "phone": "5525277660",
                "normalized_phone": "5525277660",
                "email_opt_in": True,
                "whatsapp_opt_in": True,
                "email_unsubscribed": False,
                "whatsapp_unsubscribed": False,
                "interest_status": "unknown",
                "first_seen_at": "2026-03-05T20:32:07+00:00",
                "last_seen_at": "2026-03-17T22:54:38+00:00",
            }
        ],
        "client_profiles": [{"client_id": "client_1", "country": "Mexico"}],
    }
    module._resolve_client_country_code.cache_clear()
    module.supabase = _FakeSupabase(state)
    supabase = _FakeSupabase(state)

    assert upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_1",
        email="aldo@example.com",
        phone="+525525277660",
        interest_status="interested",
        seen_at="2026-03-18T20:36:17+00:00",
    )

    assert len(state["rows"]) == 1
    assert state["rows"][0]["phone"] == "+525525277660"
    assert state["rows"][0]["normalized_phone"] == "+525525277660"
    assert state["rows"][0]["interest_status"] == "interested"
    assert state["rows"][0]["last_seen_at"] == "2026-03-18T20:36:17+00:00"


def test_non_mx_local_phone_is_not_auto_promoted():
    state = {
        "rows": [],
        "client_profiles": [{"client_id": "client_uk", "country": "United Kingdom"}],
    }
    module._resolve_client_country_code.cache_clear()
    module.supabase = _FakeSupabase(state)
    supabase = _FakeSupabase(state)

    assert not upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id="client_uk",
        phone="2079460128",
        interest_status="interested",
        seen_at="2026-03-18T20:36:17+00:00",
    )
    assert state["rows"] == []
