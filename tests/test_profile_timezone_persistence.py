import asyncio
from types import SimpleNamespace


class _FakeTable:
    def __init__(self, table_name: str, state: dict):
        self._table_name = table_name
        self._state = state
        self._op = None
        self._payload = None
        self._select_query = None
        self._maybe_single = False
        self._single = False

    def select(self, query):
        self._op = "select"
        self._select_query = query
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def single(self):
        self._single = True
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        self._state["calls"].append(
            {
                "op": "upsert",
                "table": self._table_name,
                "payload": payload,
                "on_conflict": on_conflict,
            }
        )
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        self._state["calls"].append(
            {
                "op": "update",
                "table": self._table_name,
                "payload": payload,
                "on_conflict": None,
            }
        )
        return self

    def execute(self):
        if self._op == "select":
            if self._table_name == "client_settings" and self._maybe_single:
                plan_id = self._state.get("plan_id")
                return SimpleNamespace(data={"plan_id": plan_id} if plan_id else None)
            if self._table_name == "plans" and self._single:
                return SimpleNamespace(data={"id": "premium"})
            return SimpleNamespace(data=[])
        if self._op in {"upsert", "update"}:
            return SimpleNamespace(data=[self._payload])
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, *, plan_id: str | None = "premium"):
        self.state = {"calls": [], "plan_id": plan_id}

    def table(self, table_name: str):
        return _FakeTable(table_name, self.state)


class _DummyRequest:
    def __init__(self, payload: dict | None = None):
        self._payload = payload or {}
        self.headers = {}
        self.client = SimpleNamespace(host="127.0.0.1")

    async def json(self):
        return self._payload


def test_complete_onboarding_missing_timezone_does_not_force_utc(monkeypatch):
    from api.routes import onboarding

    fake_supabase = _FakeSupabase()
    monkeypatch.setattr(onboarding, "supabase", fake_supabase)
    monkeypatch.setattr(onboarding, "authorize_client_request", lambda _request, _client_id: None)

    payload = onboarding.CompleteOnboardingRequest(
        client_id="client-1",
        profile=onboarding.ProfileData(contact_name="Alice Doe"),
        terms=onboarding.TermsData(accepted=True, accepted_marketing=False),
    )

    result = asyncio.run(onboarding.complete_onboarding(payload, _DummyRequest()))
    assert result["success"] is True

    timezone_writes = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings"
    ]
    assert timezone_writes == []


def test_complete_onboarding_with_timezone_upserts_timezone(monkeypatch):
    from api.routes import onboarding

    fake_supabase = _FakeSupabase()
    monkeypatch.setattr(onboarding, "supabase", fake_supabase)
    monkeypatch.setattr(onboarding, "authorize_client_request", lambda _request, _client_id: None)

    payload = onboarding.CompleteOnboardingRequest(
        client_id="client-1",
        profile=onboarding.ProfileData(
            contact_name="Alice Doe",
            timezone="America/New_York",
        ),
        terms=onboarding.TermsData(accepted=True, accepted_marketing=False),
    )

    result = asyncio.run(onboarding.complete_onboarding(payload, _DummyRequest()))
    assert result["success"] is True

    timezone_writes = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings" and call["op"] == "upsert"
    ]
    assert len(timezone_writes) == 1
    assert timezone_writes[0]["payload"]["timezone"] == "America/New_York"


def test_complete_onboarding_persists_business_sector_and_discovery_source(monkeypatch):
    from api.routes import onboarding

    fake_supabase = _FakeSupabase()
    monkeypatch.setattr(onboarding, "supabase", fake_supabase)
    monkeypatch.setattr(onboarding, "authorize_client_request", lambda _request, _client_id: None)

    payload = onboarding.CompleteOnboardingRequest(
        client_id="client-1",
        profile=onboarding.ProfileData(
            contact_name="Alice Doe",
            industry="Healthcare",
            discovery_source="Instagram",
        ),
        terms=onboarding.TermsData(accepted=True, accepted_marketing=False),
    )

    result = asyncio.run(onboarding.complete_onboarding(payload, _DummyRequest()))
    assert result["success"] is True

    profile_writes = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_profile" and call["op"] == "upsert"
    ]
    assert len(profile_writes) == 1
    assert profile_writes[0]["payload"]["industry"] == "Healthcare"
    assert profile_writes[0]["payload"]["discovery_source"] == "Instagram"


def test_client_settings_language_update_does_not_apply_model_defaults(monkeypatch):
    import api.client_settings_api as client_settings_api

    fake_supabase = _FakeSupabase(plan_id="premium")
    monkeypatch.setattr(client_settings_api, "supabase", fake_supabase)
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(client_settings_api, "client_has_active_feature", lambda *_args, **_kwargs: True)

    request = _DummyRequest({"client_id": "client-1", "language": "en"})
    response = asyncio.run(client_settings_api.upsert_client_settings(request))
    assert response.status_code == 200

    settings_upserts = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings" and call["op"] == "upsert"
    ]
    assert len(settings_upserts) == 1
    payload = settings_upserts[0]["payload"]

    assert payload["client_id"] == "client-1"
    assert payload["language"] == "en"
    assert payload["plan_id"] == "premium"
    assert "assistant_name" not in payload
    assert "temperature" not in payload
    assert "show_powered_by" not in payload
    assert "session_message_limit" not in payload


def test_client_settings_free_plan_does_not_persist_launcher_icon(monkeypatch):
    import api.client_settings_api as client_settings_api

    fake_supabase = _FakeSupabase(plan_id="free")
    monkeypatch.setattr(client_settings_api, "supabase", fake_supabase)
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(client_settings_api, "client_has_active_feature", lambda *_args, **_kwargs: False)

    request = _DummyRequest(
        {
            "client_id": "client-1",
            "launcher_icon_url": "https://cdn.example.com/widget-icon.png",
        }
    )
    response = asyncio.run(client_settings_api.upsert_client_settings(request))
    assert response.status_code == 200

    settings_upserts = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings" and call["op"] == "upsert"
    ]
    assert len(settings_upserts) == 1
    payload = settings_upserts[0]["payload"]

    assert payload["client_id"] == "client-1"
    assert payload["plan_id"] == "free"
    assert "launcher_icon_url" not in payload


def test_client_settings_premium_without_widget_feature_does_not_persist_widget_theme(monkeypatch):
    import api.client_settings_api as client_settings_api

    fake_supabase = _FakeSupabase(plan_id="premium")
    monkeypatch.setattr(client_settings_api, "supabase", fake_supabase)
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(client_settings_api, "client_has_active_feature", lambda *_args, **_kwargs: False)

    request = _DummyRequest(
        {
            "client_id": "client-1",
            "header_color": "#000000",
            "button_color": "#123456",
        }
    )
    response = asyncio.run(client_settings_api.upsert_client_settings(request))
    assert response.status_code == 200

    settings_upserts = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings" and call["op"] == "upsert"
    ]
    assert len(settings_upserts) == 1
    payload = settings_upserts[0]["payload"]

    assert payload["client_id"] == "client-1"
    assert payload["plan_id"] == "premium"
    assert "header_color" not in payload
    assert "button_color" not in payload


def test_client_settings_with_widget_feature_persists_widget_theme(monkeypatch):
    import api.client_settings_api as client_settings_api

    fake_supabase = _FakeSupabase(plan_id="premium")
    monkeypatch.setattr(client_settings_api, "supabase", fake_supabase)
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(client_settings_api, "client_has_active_feature", lambda *_args, **_kwargs: True)

    request = _DummyRequest(
        {
            "client_id": "client-1",
            "header_color": "#000000",
            "button_color": "#123456",
        }
    )
    response = asyncio.run(client_settings_api.upsert_client_settings(request))
    assert response.status_code == 200

    settings_upserts = [
        call for call in fake_supabase.state["calls"]
        if call["table"] == "client_settings" and call["op"] == "upsert"
    ]
    assert len(settings_upserts) == 1
    payload = settings_upserts[0]["payload"]

    assert payload["header_color"] == "#000000"
    assert payload["button_color"] == "#123456"
