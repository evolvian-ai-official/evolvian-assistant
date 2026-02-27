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
