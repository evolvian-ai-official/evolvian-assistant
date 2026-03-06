import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.getcwd())


def test_load_campaign_opt_out_labels_ignores_interest_quick_reply(monkeypatch):
    from api.modules.whatsapp import webhook as module

    state = {
        "marketing_campaigns": [
            {"id": "campaign_1", "client_id": "client_1", "meta_template_id": "meta_1"},
        ],
        "meta_approved_templates": [
            {
                "id": "meta_1",
                "buttons_json": {
                    "buttons": [
                        {"type": "QUICK_REPLY", "text": "Me interesa", "purpose": "interest"},
                        {"type": "QUICK_REPLY", "text": "No recibir más", "purpose": "opt_out"},
                    ]
                },
            }
        ],
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.filters = {}
            self.mode = "select"

        def select(self, _fields):
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
            return self

        def execute(self):
            rows = state.get(self.table_name, [])
            filtered = [
                row for row in rows
                if all(row.get(k) == v for k, v in self.filters.items())
            ]
            return SimpleNamespace(data=filtered)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    labels = module._load_campaign_opt_out_labels("client_1", "campaign_1")
    assert labels == {"no recibir mas"}


def test_load_campaign_opt_out_labels_legacy_single_button_fallback(monkeypatch):
    from api.modules.whatsapp import webhook as module

    state = {
        "marketing_campaigns": [
            {"id": "campaign_2", "client_id": "client_1", "meta_template_id": "meta_2"},
        ],
        "meta_approved_templates": [
            {
                "id": "meta_2",
                "buttons_json": {
                    "buttons": [
                        {"type": "QUICK_REPLY", "text": "Salir"},
                    ]
                },
            }
        ],
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.filters = {}

        def select(self, _fields):
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
            return self

        def execute(self):
            rows = state.get(self.table_name, [])
            filtered = [
                row for row in rows
                if all(row.get(k) == v for k, v in self.filters.items())
            ]
            return SimpleNamespace(data=filtered)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    labels = module._load_campaign_opt_out_labels("client_1", "campaign_2")
    assert labels == {"salir"}


def test_load_campaign_opt_out_labels_single_interest_with_purpose_is_not_opt_out(monkeypatch):
    from api.modules.whatsapp import webhook as module

    state = {
        "marketing_campaigns": [
            {"id": "campaign_3", "client_id": "client_1", "meta_template_id": "meta_3"},
        ],
        "meta_approved_templates": [
            {
                "id": "meta_3",
                "buttons_json": {
                    "buttons": [
                        {"type": "QUICK_REPLY", "text": "Me interesa", "purpose": "interest"},
                    ]
                },
            }
        ],
    }

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self.filters = {}

        def select(self, _fields):
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def limit(self, _n):
            return self

        def execute(self):
            rows = state.get(self.table_name, [])
            filtered = [
                row for row in rows
                if all(row.get(k) == v for k, v in self.filters.items())
            ]
            return SimpleNamespace(data=filtered)

    class _FakeSupabase:
        def table(self, table_name: str):
            return _FakeQuery(table_name)

    monkeypatch.setattr(module, "supabase", _FakeSupabase())
    labels = module._load_campaign_opt_out_labels("client_1", "campaign_3")
    assert labels == set()
