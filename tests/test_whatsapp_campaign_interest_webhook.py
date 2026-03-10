import asyncio
import os
import sys


sys.path.insert(0, os.getcwd())


def test_whatsapp_campaign_interest_creates_handoff_and_skips_rag(monkeypatch):
    from api.modules.assistant_rag import intent_router
    from api.modules.whatsapp import webhook as module

    handoff_calls = []
    send_calls = []
    event_calls = []

    monkeypatch.setattr(module, "get_channel_by_wa_phone_id", lambda *_args, **_kwargs: {"client_id": "client_1"})
    monkeypatch.setattr(module, "is_duplicate_wa_message", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(module, "register_wa_message", lambda **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_load_recent_marketing_recipient",
        lambda **_kwargs: {
            "campaign_id": "campaign_1",
            "recipient_key": "phone:+5215512345678",
            "provider_message_id": "wamid.sent_campaign",
        },
    )
    monkeypatch.setattr(module, "_load_campaign_opt_out_labels", lambda *_args, **_kwargs: {"no recibir más"})
    monkeypatch.setattr(
        module,
        "_log_marketing_interest_event",
        lambda **kwargs: event_calls.append(kwargs),
    )

    async def _fake_send_whatsapp_message(*, to_number, text, channel):
        send_calls.append({"to_number": to_number, "text": text, "channel": channel})
        return True

    async def _fail_handle_message(**_kwargs):
        raise AssertionError("RAG should not be called for campaign-interest handoff flow")

    monkeypatch.setattr(module, "send_whatsapp_message", _fake_send_whatsapp_message)
    monkeypatch.setattr(module, "handle_message", _fail_handle_message)
    monkeypatch.setattr(
        intent_router,
        "_upsert_whatsapp_handoff",
        lambda **kwargs: handoff_calls.append(kwargs)
        or {"feature_enabled": True, "handoff_id": "handoff_123", "alert_created": True},
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "wa_phone_1"},
                            "messages": [
                                {
                                    "id": "wamid.inbound_1",
                                    "from": "5215512345678",
                                    "type": "button",
                                    "button": {"text": "Me interesa"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    asyncio.run(module.process_whatsapp_payload(payload))

    assert len(handoff_calls) == 1
    assert handoff_calls[0]["reason"] == "campaign_interest"
    assert handoff_calls[0]["trigger"] == "campaign_interest_button"
    assert len(event_calls) == 1
    assert event_calls[0]["campaign_id"] == "campaign_1"
    assert len(send_calls) == 1
    assert "asesor humano" in send_calls[0]["text"].lower()


def test_whatsapp_campaign_interest_button_without_text_still_creates_handoff(monkeypatch):
    from api.modules.assistant_rag import intent_router
    from api.modules.whatsapp import webhook as module

    handoff_calls = []
    send_calls = []

    monkeypatch.setattr(module, "get_channel_by_wa_phone_id", lambda *_args, **_kwargs: {"client_id": "client_1"})
    monkeypatch.setattr(module, "is_duplicate_wa_message", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(module, "register_wa_message", lambda **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_load_recent_marketing_recipient",
        lambda **_kwargs: {
            "campaign_id": "campaign_1",
            "recipient_key": "phone:+5215512345678",
            "provider_message_id": "wamid.sent_campaign",
        },
    )
    monkeypatch.setattr(module, "_load_campaign_opt_out_labels", lambda *_args, **_kwargs: {"no recibir más"})
    monkeypatch.setattr(module, "_log_marketing_interest_event", lambda **_kwargs: None)

    async def _fake_send_whatsapp_message(*, to_number, text, channel):
        send_calls.append({"to_number": to_number, "text": text, "channel": channel})
        return True

    async def _fail_handle_message(**_kwargs):
        raise AssertionError("RAG should not be called for campaign-interest handoff flow")

    monkeypatch.setattr(module, "send_whatsapp_message", _fake_send_whatsapp_message)
    monkeypatch.setattr(module, "handle_message", _fail_handle_message)
    monkeypatch.setattr(
        intent_router,
        "_upsert_whatsapp_handoff",
        lambda **kwargs: handoff_calls.append(kwargs)
        or {"feature_enabled": True, "handoff_id": "handoff_123", "alert_created": True},
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "wa_phone_1"},
                            "messages": [
                                {
                                    "id": "wamid.inbound_2",
                                    "from": "5215512345678",
                                    "type": "button",
                                    "button": {},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    asyncio.run(module.process_whatsapp_payload(payload))

    assert len(handoff_calls) == 1
    assert handoff_calls[0]["reason"] == "campaign_interest"
    assert handoff_calls[0]["trigger"] == "campaign_interest_button"
    assert len(send_calls) == 1


def test_whatsapp_no_reply_policy_skips_send(monkeypatch):
    from api.modules.whatsapp import webhook as module

    send_calls = []

    monkeypatch.setattr(module, "get_channel_by_wa_phone_id", lambda *_args, **_kwargs: {"client_id": "client_1"})
    monkeypatch.setattr(module, "is_duplicate_wa_message", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(module, "register_wa_message", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_load_recent_marketing_recipient", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_load_campaign_opt_out_labels", lambda *_args, **_kwargs: set())

    async def _fake_send_whatsapp_message(*, to_number, text, channel):
        send_calls.append({"to_number": to_number, "text": text, "channel": channel})
        return True

    async def _no_reply_handle_message(**_kwargs):
        return None

    monkeypatch.setattr(module, "send_whatsapp_message", _fake_send_whatsapp_message)
    monkeypatch.setattr(module, "handle_message", _no_reply_handle_message)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "wa_phone_1"},
                            "messages": [
                                {
                                    "id": "wamid.inbound_nr_1",
                                    "from": "5215512345678",
                                    "type": "text",
                                    "text": {"body": "Gracias por comunicarte con Dental Del Centro"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    asyncio.run(module.process_whatsapp_payload(payload))

    assert len(send_calls) == 0
