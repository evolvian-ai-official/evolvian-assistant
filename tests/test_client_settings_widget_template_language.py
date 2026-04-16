import json
import sys
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeTable:
    def __init__(self, table_name: str, state: dict):
        self._table_name = table_name
        self._state = state
        self._filters = {}
        self._single = False
        self._maybe_single = False
        self._limit = None
        self._order_field = None
        self._order_desc = False

    def select(self, _query):
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def limit(self, value):
        self._limit = value
        return self

    def order(self, field, desc=False):
        self._order_field = field
        self._order_desc = desc
        return self

    def execute(self):
        if self._table_name == "client_settings":
            row = dict(self._state["client_settings"])
            return SimpleNamespace(data=row)

        if self._table_name == "message_templates":
            rows = [
                dict(row)
                for row in self._state["message_templates"]
                if all(row.get(field) == value for field, value in self._filters.items())
            ]
            if self._order_field:
                rows.sort(key=lambda row: row.get(self._order_field) or "", reverse=self._order_desc)
            if self._limit is not None:
                rows = rows[: self._limit]
            return SimpleNamespace(data=rows)

        if self._table_name == "plans":
            if self._maybe_single:
                return SimpleNamespace(data=None)
            return SimpleNamespace(data=[])

        if self._table_name == "clients":
            return SimpleNamespace(data={"id": self._state["client_settings"]["client_id"]})

        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, state: dict):
        self._state = state

    def table(self, table_name: str):
        return _FakeTable(table_name, self._state)


class _DummyRequest:
    headers = {}
    client = SimpleNamespace(host="127.0.0.1")


def _load_response_body(response):
    return json.loads(response.body.decode("utf-8"))


def test_client_settings_returns_widget_template_matching_requested_language(monkeypatch):
    import api.client_settings_api as client_settings_api

    state = {
        "client_settings": {
            "client_id": "client-1",
            "assistant_name": "Assistant",
            "language": "es",
            "appointments_template_language": "es",
            "show_powered_by": True,
            "show_logo": True,
            "require_email": False,
            "require_phone": False,
            "require_terms": False,
            "show_tooltip": False,
            "show_legal_links": False,
            "require_email_consent": False,
            "require_terms_consent": False,
            "plan_id": "free",
            "plan": {"id": "free", "plan_features": []},
        },
        "message_templates": [
            {
                "id": "tpl-es",
                "client_id": "client-1",
                "channel": "widget",
                "type": "opening_message",
                "is_active": True,
                "label": "ES",
                "body": "Hola desde widget",
                "language_family": "es",
                "locale_code": "es_MX",
                "updated_at": "2026-03-13T10:00:00Z",
            },
            {
                "id": "tpl-en",
                "client_id": "client-1",
                "channel": "widget",
                "type": "opening_message",
                "is_active": True,
                "label": "EN",
                "body": "Hello from widget",
                "language_family": "en",
                "locale_code": "en_US",
                "updated_at": "2026-03-13T09:00:00Z",
            },
        ],
    }

    monkeypatch.setattr(client_settings_api, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        client_settings_api,
        "resolve_effective_plan_id",
        lambda client_id, base_plan_id, supabase_client: base_plan_id,
    )

    response = client_settings_api.get_client_settings(
        _DummyRequest(),
        client_id="client-1",
        language="en",
    )
    payload = _load_response_body(response)

    assert payload["widget_opening_template"]["id"] == "tpl-en"
    assert payload["widget_opening_template"]["body"] == "Hello from widget"
    assert payload["widget_opening_template"]["language_family"] == "en"


def test_client_settings_uses_client_language_for_widget_template_when_not_overridden(monkeypatch):
    import api.client_settings_api as client_settings_api

    state = {
        "client_settings": {
            "client_id": "client-1",
            "assistant_name": "Assistant",
            "language": "es",
            "appointments_template_language": "es",
            "show_powered_by": True,
            "show_logo": True,
            "require_email": False,
            "require_phone": False,
            "require_terms": False,
            "show_tooltip": False,
            "show_legal_links": False,
            "require_email_consent": False,
            "require_terms_consent": False,
            "plan_id": "free",
            "plan": {"id": "free", "plan_features": []},
        },
        "message_templates": [
            {
                "id": "tpl-en",
                "client_id": "client-1",
                "channel": "widget",
                "type": "opening_message",
                "is_active": True,
                "label": "EN",
                "body": "Hello from widget",
                "language_family": "en",
                "locale_code": "en_US",
                "updated_at": "2026-03-13T10:00:00Z",
            },
            {
                "id": "tpl-es",
                "client_id": "client-1",
                "channel": "widget",
                "type": "opening_message",
                "is_active": True,
                "label": "ES",
                "body": "Hola desde widget",
                "language_family": "es",
                "locale_code": "es_MX",
                "updated_at": "2026-03-13T09:00:00Z",
            },
        ],
    }

    monkeypatch.setattr(client_settings_api, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        client_settings_api,
        "resolve_effective_plan_id",
        lambda client_id, base_plan_id, supabase_client: base_plan_id,
    )

    response = client_settings_api.get_client_settings(_DummyRequest(), client_id="client-1")
    payload = _load_response_body(response)

    assert payload["widget_opening_template"]["id"] == "tpl-es"
    assert payload["widget_opening_template"]["body"] == "Hola desde widget"
    assert payload["widget_opening_template"]["language_family"] == "es"


def test_client_settings_free_plan_hides_custom_launcher_icon(monkeypatch):
    import api.client_settings_api as client_settings_api

    state = {
        "client_settings": {
            "client_id": "client-1",
            "assistant_name": "Assistant",
            "language": "es",
            "appointments_template_language": "es",
            "show_powered_by": True,
            "show_logo": True,
            "require_email": False,
            "require_phone": False,
            "require_terms": False,
            "show_tooltip": False,
            "show_legal_links": False,
            "require_email_consent": False,
            "require_terms_consent": False,
            "launcher_icon_url": "https://cdn.example.com/premium-icon.png",
            "plan_id": "free",
            "plan": {"id": "free", "plan_features": []},
        },
        "message_templates": [],
    }

    monkeypatch.setattr(client_settings_api, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        client_settings_api,
        "resolve_effective_plan_id",
        lambda client_id, base_plan_id, supabase_client: base_plan_id,
    )

    response = client_settings_api.get_client_settings(_DummyRequest(), client_id="client-1")
    payload = _load_response_body(response)

    assert payload["launcher_icon_url"] is None


def test_client_settings_masks_widget_theme_without_widget_customization_feature(monkeypatch):
    import api.client_settings_api as client_settings_api

    state = {
        "client_settings": {
            "client_id": "client-1",
            "assistant_name": "Assistant",
            "language": "es",
            "appointments_template_language": "es",
            "show_powered_by": False,
            "show_logo": False,
            "header_color": "#101010",
            "button_color": "#202020",
            "launcher_icon_url": "https://cdn.example.com/premium-icon.png",
            "plan_id": "premium",
            "plan": {"id": "premium", "plan_features": ["chat_widget"]},
        },
        "message_templates": [],
    }

    monkeypatch.setattr(client_settings_api, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        client_settings_api,
        "resolve_effective_plan_id",
        lambda client_id, base_plan_id, supabase_client: base_plan_id,
    )

    response = client_settings_api.get_client_settings(_DummyRequest(), client_id="client-1")
    payload = _load_response_body(response)

    assert payload["header_color"] == "#fff9f0"
    assert payload["button_color"] == "#f5a623"
    assert payload["show_powered_by"] is True
    assert payload["show_logo"] is True
    assert payload["launcher_icon_url"] is None


def test_client_settings_keeps_widget_theme_with_widget_customization_feature(monkeypatch):
    import api.client_settings_api as client_settings_api

    state = {
        "client_settings": {
            "client_id": "client-1",
            "assistant_name": "Assistant",
            "language": "es",
            "appointments_template_language": "es",
            "show_powered_by": False,
            "show_logo": False,
            "header_color": "#101010",
            "button_color": "#202020",
            "launcher_icon_url": "https://cdn.example.com/premium-icon.png",
            "plan_id": "premium",
            "plan": {"id": "premium", "plan_features": ["chat_widget", "widget_customization"]},
        },
        "message_templates": [],
    }

    monkeypatch.setattr(client_settings_api, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(client_settings_api, "authorize_client_request", lambda _request, _client_id: None)
    monkeypatch.setattr(
        client_settings_api,
        "resolve_effective_plan_id",
        lambda client_id, base_plan_id, supabase_client: base_plan_id,
    )

    response = client_settings_api.get_client_settings(_DummyRequest(), client_id="client-1")
    payload = _load_response_body(response)

    assert payload["header_color"] == "#101010"
    assert payload["button_color"] == "#202020"
    assert payload["show_powered_by"] is False
    assert payload["show_logo"] is False
    assert payload["launcher_icon_url"] == "https://cdn.example.com/premium-icon.png"
