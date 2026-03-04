from types import SimpleNamespace


class _DummyRequest:
    def __init__(self):
        self.headers = {"user-agent": "pytest-agent"}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_unsubscribe_uses_fallback_when_primary_insert_fails(monkeypatch):
    from api.public import privacy as module

    state = {"fallback_payload": None}

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

    response = module.unsubscribe_marketing_email(
        request=_DummyRequest(),
        email="aldo.benitez.cortes@gmail.com",
        client_id="ce09c2dc-fa5f-48d7-82b7-95a09213c2d9",
        language="en",
    )

    assert response.status_code == 200
    assert state["fallback_payload"] is not None
    assert state["fallback_payload"]["email"] == "aldo.benitez.cortes@gmail.com"
    assert state["fallback_payload"]["source"] == "privacy_unsubscribe_fallback"


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
