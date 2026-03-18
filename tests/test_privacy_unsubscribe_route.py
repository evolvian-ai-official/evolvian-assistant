from types import SimpleNamespace


class _DummyRequest:
    def __init__(self):
        self.headers = {"user-agent": "pytest-agent"}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_unsubscribe_uses_fallback_when_primary_insert_fails(monkeypatch):
    from api.public import privacy as module

    state = {"fallback_payload": None, "marketing_updates": []}

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self.op = None
            self.payload = None

        def select(self, *_args, **_kwargs):
            self.op = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def insert(self, payload):
            self.op = "insert"
            self.payload = payload
            return self

        def execute(self):
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "select":
                return SimpleNamespace(data=[])
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "insert":
                raise Exception("primary_insert_failed")
            if self.name == "contactame" and self.op == "insert":
                state["fallback_payload"] = dict(self.payload or {})
                return SimpleNamespace(data=[{"id": "fallback_1"}])
            raise AssertionError(f"Unexpected operation: {self.name}:{self.op}")

    class _FakeSupabase:
        def table(self, name: str):
            return _FakeTable(name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")
    monkeypatch.setattr(
        module,
        "upsert_marketing_contact_state",
        lambda **kwargs: state["marketing_updates"].append(kwargs) or True,
    )

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert state["fallback_payload"] is not None
    assert state["fallback_payload"]["email"] == "aldo.benitez.cortes@gmail.com"
    assert state["fallback_payload"]["interested_plan"] == module.CONTACTAME_FALLBACK_PLAN
    assert state["fallback_payload"]["source"] == "privacy_unsubscribe_fallback"
    assert len(state["marketing_updates"]) == 1
    assert state["marketing_updates"][0]["email_unsubscribed"] is True


def test_unsubscribe_treats_duplicate_race_as_success(monkeypatch):
    from api.public import privacy as module

    state = {"select_calls": 0, "fallback_calls": 0}

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self.op = None

        def select(self, *_args, **_kwargs):
            self.op = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def insert(self, _payload):
            self.op = "insert"
            return self

        def execute(self):
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "select":
                state["select_calls"] += 1
                if state["select_calls"] == 1:
                    return SimpleNamespace(data=[])
                return SimpleNamespace(data=[{"id": "row1", "status": "pending", "details": None}])
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "insert":
                raise Exception("duplicate_key")
            if self.name == "contactame" and self.op == "insert":
                state["fallback_calls"] += 1
                return SimpleNamespace(data=[{"id": "fallback_1"}])
            raise AssertionError(f"Unexpected operation: {self.name}:{self.op}")

    class _FakeSupabase:
        def table(self, name: str):
            return _FakeTable(name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert state["select_calls"] >= 2
    assert state["fallback_calls"] == 0


def test_unsubscribe_updates_existing_contactame_row_when_fallback_insert_is_duplicate(monkeypatch):
    from api.public import privacy as module

    state = {"updated_email": None, "updated_payload": None}

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self.op = None
            self.payload = None
            self.eq_filters = []

        def select(self, *_args, **_kwargs):
            self.op = "select"
            return self

        def eq(self, column, value):
            self.eq_filters.append((column, value))
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def insert(self, payload):
            self.op = "insert"
            self.payload = payload
            return self

        def update(self, payload):
            self.op = "update"
            self.payload = payload
            return self

        def execute(self):
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "select":
                return SimpleNamespace(data=[])
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "insert":
                raise Exception("primary_insert_failed")
            if self.name == "contactame" and self.op == "insert":
                raise Exception("duplicate key value violates unique constraint contactame_email_key")
            if self.name == "contactame" and self.op == "update":
                state["updated_payload"] = dict(self.payload or {})
                state["updated_email"] = dict(self.eq_filters).get("email")
                return SimpleNamespace(data=[{"id": "contact_1"}])
            raise AssertionError(f"Unexpected operation: {self.name}:{self.op}")

    class _FakeSupabase:
        def table(self, name: str):
            return _FakeTable(name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert state["updated_email"] == "aldo.benitez.cortes@gmail.com"
    assert state["updated_payload"] is not None
    assert state["updated_payload"]["source"] == "privacy_unsubscribe_fallback"


def test_unsubscribe_uses_legacy_contactame_payload_when_extended_fields_are_unavailable(monkeypatch):
    from api.public import privacy as module

    state = {"insert_payloads": []}

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self.op = None
            self.payload = None

        def select(self, *_args, **_kwargs):
            self.op = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def insert(self, payload):
            self.op = "insert"
            self.payload = payload
            return self

        def update(self, payload):
            self.op = "update"
            self.payload = payload
            return self

        def execute(self):
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "select":
                return SimpleNamespace(data=[])
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "insert":
                raise Exception("primary_insert_failed")
            if self.name == "contactame" and self.op == "insert":
                state["insert_payloads"].append(dict(self.payload or {}))
                if len(state["insert_payloads"]) == 1:
                    raise Exception("column ip_address does not exist")
                return SimpleNamespace(data=[{"id": "fallback_legacy"}])
            raise AssertionError(f"Unexpected operation: {self.name}:{self.op}")

    class _FakeSupabase:
        def table(self, name: str):
            return _FakeTable(name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert len(state["insert_payloads"]) == 2
    assert "ip_address" in state["insert_payloads"][0]
    assert "ip_address" not in state["insert_payloads"][1]


def test_unsubscribe_uses_legacy_update_when_duplicate_row_exists_on_legacy_contactame_schema(monkeypatch):
    from api.public import privacy as module

    state = {"update_payloads": []}

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self.op = None
            self.payload = None

        def select(self, *_args, **_kwargs):
            self.op = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def insert(self, payload):
            self.op = "insert"
            self.payload = payload
            return self

        def update(self, payload):
            self.op = "update"
            self.payload = payload
            return self

        def execute(self):
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "select":
                return SimpleNamespace(data=[])
            if self.name == module.PRIVACY_REQUEST_TABLE and self.op == "insert":
                raise Exception("primary_insert_failed")
            if self.name == "contactame" and self.op == "insert":
                raise Exception("duplicate key value violates unique constraint contactame_email_key")
            if self.name == "contactame" and self.op == "update":
                state["update_payloads"].append(dict(self.payload or {}))
                if len(state["update_payloads"]) == 1:
                    raise Exception("column ip_address does not exist")
                return SimpleNamespace(data=[{"id": "contact_legacy"}])
            raise AssertionError(f"Unexpected operation: {self.name}:{self.op}")

    class _FakeSupabase:
        def table(self, name: str):
            return _FakeTable(name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    monkeypatch.setattr(module, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(module, "get_request_ip", lambda _request: "127.0.0.1")

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert len(state["update_payloads"]) == 2
    assert "ip_address" in state["update_payloads"][0]
    assert "ip_address" not in state["update_payloads"][1]
