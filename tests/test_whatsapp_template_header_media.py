import asyncio
import os
import sys


sys.path.insert(0, os.getcwd())


def test_resolve_effective_template_buttons_json_prefers_local_header_override():
    from api.modules.whatsapp import template_sync as module

    canonical = {
        "buttons": [{"type": "QUICK_REPLY", "text": "Cancelar"}],
        "header": {"type": "IMAGE", "image_url": "https://cdn.example.com/global.png"},
    }
    local = {
        "header": {"type": "IMAGE", "image_url": "https://cdn.example.com/client.png"},
    }

    resolved = module.resolve_effective_template_buttons_json(
        canonical_buttons_json=canonical,
        local_buttons_json=local,
    )

    assert resolved == {
        "buttons": [{"type": "QUICK_REPLY", "text": "Cancelar"}],
        "header": {"type": "IMAGE", "image_url": "https://cdn.example.com/client.png"},
    }


def test_build_client_template_name_versions_only_when_local_override_exists():
    from api.modules.whatsapp import template_sync as module

    base = module.build_client_template_name("appointment_reminder", "client_1")
    with_override_a = module.build_client_template_name(
        "appointment_reminder",
        "client_1",
        {"header": {"type": "IMAGE", "image_url": "https://cdn.example.com/a.png"}},
    )
    with_override_b = module.build_client_template_name(
        "appointment_reminder",
        "client_1",
        {"header": {"type": "IMAGE", "image_url": "https://cdn.example.com/b.png"}},
    )

    assert base == "appointment_reminder"
    assert with_override_a.startswith("appointment_reminder_cfg_")
    assert with_override_b.startswith("appointment_reminder_cfg_")
    assert with_override_a != with_override_b


def test_send_meta_template_builds_header_component_from_buttons_json(monkeypatch):
    from api.modules.whatsapp import whatsapp_sender as module

    captured = {}

    class _FakeResponse:
        status_code = 200
        text = '{"messages":[{"id":"wamid.123"}]}'

        def json(self):
            return {"messages": [{"id": "wamid.123"}]}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        module.send_meta_template(
            to_number="+5215512345678",
            template_name="appointment_reminder_cfg_123",
            language_code="es_MX",
            parameters=["Ada", "Consulta - 10:00"],
            buttons_json={
                "header": {
                    "type": "IMAGE",
                    "image_url": "https://cdn.example.com/header.png",
                }
            },
            phone_number_id="123456",
            access_token="token_123",
        )
    )

    assert result["success"] is True
    assert captured["json"]["type"] == "template"
    assert captured["json"]["template"]["components"][0] == {
        "type": "header",
        "parameters": [
            {
                "type": "image",
                "image": {"link": "https://cdn.example.com/header.png"},
            }
        ],
    }
