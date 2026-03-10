from datetime import datetime, timedelta, timezone
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.getcwd())


def _build_client():
    from api import meta_webhook as module

    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app), module


def test_messenger_event_uses_shared_flow_and_sender_session(monkeypatch):
    client, module = _build_client()
    process_calls = []
    send_calls = []

    monkeypatch.setattr(module, "verify_meta_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "resolve_social_channel_credentials",
        lambda **_kwargs: {
            "client_id": "client_1",
            "meta_entity_id": "page_123",
            "access_token": "token_123",
        },
    )

    async def _fake_process_user_message(**kwargs):
        process_calls.append(kwargs)
        return "Hello from bot"

    async def _fake_send_social_text_message(**kwargs):
        send_calls.append(kwargs)
        return {"success": True, "message_id": "mid.out.1"}

    monkeypatch.setattr(module, "process_user_message", _fake_process_user_message)
    monkeypatch.setattr(module, "send_social_text_message", _fake_send_social_text_message)

    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_123",
                "messaging": [
                    {
                        "sender": {"id": "user_abc"},
                        "recipient": {"id": "page_123"},
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "message": {"mid": "mid.in.1", "text": "Hi"},
                    }
                ],
            }
        ],
    }

    res = client.post("/webhooks/meta", json=payload)
    body = res.json()

    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["by_status"]["ok"] == 1
    assert len(process_calls) == 1
    assert process_calls[0]["client_id"] == "client_1"
    assert process_calls[0]["session_id"] == "messenger-user_abc"
    assert process_calls[0]["channel"] == "messenger"
    assert len(send_calls) == 1
    assert send_calls[0]["channel"] == "messenger"
    assert send_calls[0]["recipient_id"] == "user_abc"


def test_instagram_event_uses_instagram_channel(monkeypatch):
    client, module = _build_client()
    process_calls = []

    monkeypatch.setattr(module, "verify_meta_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "resolve_social_channel_credentials",
        lambda **_kwargs: {
            "client_id": "client_2",
            "meta_entity_id": "ig_123",
            "access_token": "token_ig",
        },
    )

    async def _fake_process_user_message(**kwargs):
        process_calls.append(kwargs)
        return "Hola"

    async def _fake_send_social_text_message(**_kwargs):
        return {"success": True, "message_id": "mid.out.ig.1"}

    monkeypatch.setattr(module, "process_user_message", _fake_process_user_message)
    monkeypatch.setattr(module, "send_social_text_message", _fake_send_social_text_message)

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "ig_123",
                "messaging": [
                    {
                        "sender": {"id": "ig_user_1"},
                        "recipient": {"id": "ig_123"},
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "message": {"mid": "mid.in.ig.1", "text": "Hola"},
                    }
                ],
            }
        ],
    }

    res = client.post("/webhooks/meta", json=payload)
    body = res.json()

    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["by_status"]["ok"] == 1
    assert len(process_calls) == 1
    assert process_calls[0]["channel"] == "instagram"
    assert process_calls[0]["session_id"] == "instagram-ig_user_1"


def test_social_stale_event_respects_24h_window(monkeypatch):
    client, module = _build_client()
    saved_rows = []

    monkeypatch.setattr(module, "verify_meta_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "resolve_social_channel_credentials",
        lambda **_kwargs: {
            "client_id": "client_3",
            "meta_entity_id": "page_stale",
            "access_token": "token_stale",
        },
    )
    async def _unexpected_process(**_kwargs):
        raise AssertionError("process_user_message should not run")

    async def _unexpected_send(**_kwargs):
        raise AssertionError("send should not run")

    monkeypatch.setattr(module, "process_user_message", _unexpected_process)
    monkeypatch.setattr(module, "send_social_text_message", _unexpected_send)
    monkeypatch.setattr(module, "save_history", lambda **kwargs: saved_rows.append(kwargs))

    stale_ts_ms = int((datetime.now(timezone.utc) - timedelta(hours=30)).timestamp() * 1000)
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_stale",
                "messaging": [
                    {
                        "sender": {"id": "user_old"},
                        "recipient": {"id": "page_stale"},
                        "timestamp": stale_ts_ms,
                        "message": {"mid": "mid.in.old", "text": "old message"},
                    }
                ],
            }
        ],
    }

    res = client.post("/webhooks/meta", json=payload)
    body = res.json()

    assert res.status_code == 200
    assert body["by_status"]["window_closed"] == 1
    assert len(saved_rows) == 1
    assert saved_rows[0]["client_id"] == "client_3"
    assert saved_rows[0]["channel"] == "messenger"


def test_messenger_no_reply_skips_send(monkeypatch):
    client, module = _build_client()

    monkeypatch.setattr(module, "verify_meta_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "resolve_social_channel_credentials",
        lambda **_kwargs: {
            "client_id": "client_4",
            "meta_entity_id": "page_777",
            "access_token": "token_777",
        },
    )

    async def _no_reply_process(**_kwargs):
        return None

    async def _unexpected_send(**_kwargs):
        raise AssertionError("send should not run when no reply is returned")

    monkeypatch.setattr(module, "process_user_message", _no_reply_process)
    monkeypatch.setattr(module, "send_social_text_message", _unexpected_send)

    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_777",
                "messaging": [
                    {
                        "sender": {"id": "user_no_reply"},
                        "recipient": {"id": "page_777"},
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "message": {"mid": "mid.in.nr.1", "text": "Gracias por comunicarte con nosotros"},
                    }
                ],
            }
        ],
    }

    res = client.post("/webhooks/meta", json=payload)
    body = res.json()

    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["by_status"]["no_reply"] == 1


def test_meta_graph_api_version_enforces_v19(monkeypatch):
    from api.modules.meta.social_sender import get_meta_graph_api_version, is_within_messaging_window

    monkeypatch.setenv("META_GRAPH_API_VERSION", "v18.0")
    assert get_meta_graph_api_version() == "v19.0"

    now = datetime.now(timezone.utc)
    assert is_within_messaging_window(now - timedelta(hours=23), window_hours=24) is True
    assert is_within_messaging_window(now - timedelta(hours=25), window_hours=24) is False


def test_whatsapp_session_id_normalizes_mx_521_variant(monkeypatch):
    client, module = _build_client()
    process_calls = []

    monkeypatch.setattr(module, "verify_meta_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "get_client_id_by_channel", lambda *_args, **_kwargs: "client_wa")
    monkeypatch.setattr(module, "get_whatsapp_credentials", lambda *_args, **_kwargs: {"wa_token": "tok", "wa_phone_id": "pid"})

    async def _fake_process_user_message(**kwargs):
        process_calls.append(kwargs)
        return "ok"

    monkeypatch.setattr(module, "process_user_message", _fake_process_user_message)
    monkeypatch.setattr(module, "send_whatsapp_message", lambda **_kwargs: True)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "15551234567"},
                            "messages": [
                                {
                                    "from": "5215512345678",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }

    res = client.post("/webhooks/meta", json=payload)
    body = res.json()

    assert res.status_code == 200
    assert body["status"] == "ok"
    assert len(process_calls) == 1
    assert process_calls[0]["session_id"] == "whatsapp-+525512345678"
