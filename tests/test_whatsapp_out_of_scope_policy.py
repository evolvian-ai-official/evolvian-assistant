import asyncio
import os
import sys


sys.path.insert(0, os.getcwd())


def _capture_save_history(calls):
    def _save(*args, **kwargs):
        role = kwargs.get("role") if "role" in kwargs else (args[2] if len(args) > 2 else None)
        content = kwargs.get("content") if "content" in kwargs else (args[3] if len(args) > 3 else None)
        calls.append({"role": role, "content": content, "kwargs": kwargs})

    return _save


def test_whatsapp_first_out_of_scope_redirect(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []
    handoff_calls = []

    monkeypatch.setattr(module, "route_message", lambda *_args, **_kwargs: "rag")
    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(module, "_last_assistant_was_scope_redirect", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        module,
        "_upsert_whatsapp_handoff",
        lambda **kwargs: handoff_calls.append(kwargs) or {"feature_enabled": True, "handoff_id": None},
    )
    monkeypatch.setattr(
        module,
        "ask_question",
        lambda *_args, **_kwargs: {
            "answer": "I don’t have information to answer this question.",
            "confidence_score": 0.2,
            "handoff_recommended": True,
            "human_intervention_recommended": True,
            "needs_human": True,
            "handoff_reason": "low_confidence",
            "confidence_reason": "rag_fallback_response",
        },
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message="Dime quién ganó el mundial de 1998",
            channel="whatsapp",
            provider="meta",
        )
    )

    assert "Puedo ayudarte con consultas relacionadas con este negocio" in result
    assert len(handoff_calls) == 0
    assert [c["role"] for c in history_calls] == ["user", "assistant"]


def test_whatsapp_second_out_of_scope_creates_handoff(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []
    handoff_calls = []

    monkeypatch.setattr(module, "route_message", lambda *_args, **_kwargs: "rag")
    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(module, "_last_assistant_was_scope_redirect", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "_upsert_whatsapp_handoff",
        lambda **kwargs: handoff_calls.append(kwargs)
        or {"feature_enabled": True, "handoff_id": "handoff_123", "alert_created": True},
    )
    monkeypatch.setattr(
        module,
        "ask_question",
        lambda *_args, **_kwargs: {
            "answer": "I don’t have information to answer this question.",
            "confidence_score": 0.2,
            "handoff_recommended": True,
            "human_intervention_recommended": True,
            "needs_human": True,
            "handoff_reason": "low_confidence",
            "confidence_reason": "rag_fallback_response",
        },
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message="Y donde compro boletos del mundial?",
            channel="whatsapp",
            provider="meta",
        )
    )

    assert "Ya lo estamos revisando con un agente humano" in result
    assert len(handoff_calls) == 1
    assert [c["role"] for c in history_calls] == ["user", "assistant"]


def test_whatsapp_explicit_human_request_escalates(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []

    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(
        module,
        "_upsert_whatsapp_handoff",
        lambda **_kwargs: {"feature_enabled": True, "handoff_id": "handoff_999", "alert_created": True},
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message="Quiero hablar con un agente humano",
            channel="whatsapp",
            provider="meta",
        )
    )

    assert "te responderemos lo más pronto posible por este mismo chat" in result
    assert [c["role"] for c in history_calls] == ["user", "assistant"]


def test_whatsapp_campaign_interest_active_skips_rag(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []

    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(
        module,
        "_get_active_campaign_interest_handoff",
        lambda *_args, **_kwargs: {"id": "handoff_campaign_1", "reason": "campaign_interest"},
    )
    monkeypatch.setattr(
        module,
        "route_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("route_message should not run")),
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message="Me interesa, ¿qué sigue?",
            channel="whatsapp",
            provider="meta",
        )
    )

    assert "asesor humano ya está dando seguimiento" in result
    assert [c["role"] for c in history_calls] == ["user", "assistant"]


def test_whatsapp_campaign_interest_active_allows_pricing_routing(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []
    route_calls = []

    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(
        module,
        "_get_active_campaign_interest_handoff",
        lambda *_args, **_kwargs: {"id": "handoff_campaign_1", "reason": "campaign_interest"},
    )
    monkeypatch.setattr(
        module,
        "route_message",
        lambda *_args, **_kwargs: route_calls.append(True) or "rag",
    )
    monkeypatch.setattr(
        module,
        "ask_question",
        lambda *_args, **_kwargs: "RAG_OK_PRICING",
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message="dame los precios del plan premium",
            channel="whatsapp",
            provider="meta",
        )
    )

    assert result.startswith("RAG_OK_PRICING")
    assert route_calls, "route_message should run for non-interest messages"

def test_whatsapp_institutional_auto_reply_is_suppressed(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []

    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(
        module,
        "route_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("route_message should not run")),
    )

    result = asyncio.run(
        module.process_user_message(
            client_id="client_1",
            session_id="whatsapp-5215512345678",
            message=(
                "Gracias por comunicarte con Dental Del Centro. "
                "En breve lo atendemos."
            ),
            channel="whatsapp",
            provider="meta",
        )
    )

    assert result is None
    assert [c["role"] for c in history_calls] == ["user"]
    metadata = history_calls[0]["kwargs"].get("metadata") or {}
    policy = metadata.get("message_policy") or {}
    assert policy.get("event") == "institutional_auto_reply_detected"


def test_whatsapp_campaign_auto_greetings_are_suppressed(monkeypatch):
    from api.modules.assistant_rag import intent_router as module

    history_calls = []

    monkeypatch.setattr(module, "save_history", _capture_save_history(history_calls))
    monkeypatch.setattr(
        module,
        "route_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("route_message should not run")),
    )

    examples = [
        (
            "Gracias por comunicarte con Nemiia Spa. "
            "¿Cómo podemos ayudarte? Restauración, belleza y magia para tu relajación. "
            "Can I help You?🪻"
        ),
        "Gracias por comunicarse con Nidra Spa. En breve nos comunicaremos con usted 😊",
    ]

    for message in examples:
        result = asyncio.run(
            module.process_user_message(
                client_id="client_1",
                session_id="whatsapp-5215512345678",
                message=message,
                channel="whatsapp",
                provider="meta",
            )
        )

        assert result is None

    assert [c["role"] for c in history_calls] == ["user", "user"]
    for call in history_calls:
        metadata = call["kwargs"].get("metadata") or {}
        policy = metadata.get("message_policy") or {}
        assert policy.get("event") == "institutional_auto_reply_detected"
