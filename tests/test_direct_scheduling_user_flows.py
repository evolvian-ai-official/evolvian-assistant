import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure project root is importable when pytest is invoked without PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Test sandbox fallback: some environments don't have Babel installed.
if "babel" not in sys.modules:
    babel_module = types.ModuleType("babel")
    babel_dates_module = types.ModuleType("babel.dates")
    babel_dates_module.format_datetime = lambda *_a, **_k: ""
    babel_dates_module.format_date = lambda *_a, **_k: ""
    babel_module.dates = babel_dates_module
    sys.modules["babel"] = babel_module
    sys.modules["babel.dates"] = babel_dates_module

from api.modules.assistant_rag import intent_router
from api import twilio_webhook
from api import meta_webhook
from api import chat_widget_api
from api.modules.assistant_rag import chat_email


DIRECT_SCHEDULING_PROMPTS = [
    "Quiero agendar una cita para mañana en la tarde",
    "Necesito reservar una cita para el viernes",
    "Me ayudas a agendar una sesión esta semana?",
    "Quisiera agendar una cita de valoración",
    "¿Tienes horarios para agendar mañana?",
    "Can I book an appointment for tomorrow morning?",
    "I want to schedule an appointment this Friday",
    "Please help me book a session next week",
    "Schedule a consultation for me",
    "Show me slots to book an appointment",
    "Quiero agendar y tengo disponibilidad el martes 10am",
    "Necesito una cita, ¿qué horario tienes hoy?",
    "Agendar cita 2026-03-10 15:00",
    "Book appointment on 2026-03-10 at 3pm",
    "Reservar horario para consulta inicial",
    "Agendar por favor, esta tarde después de las 5",
    "Necesito reagendar una cita para mañana",
    "Quiero una cita presencial, ¿puedo agendar?",
    "Appointment please, any slot tomorrow?",
    "Can you schedule me for a call?",
    "Agendar\nNombre: Ana Pérez\nEmail: ana@example.com",
    "Quiero agendar\nTel: +52 55 1234 5678\nNombre: Luis Gómez",
    "Schedule\nName: John Doe\nEmail: john@example.com",
    "I need an appointment slot and want to book directly",
    "Deseo reservar una cita directamente por este chat",
]

NON_SCHEDULING_PROMPTS = [
    "Hola, ¿qué servicios ofrecen?",
    "Qué planes tienes disponibles?",
    "Dame información sobre precios y planes",
    "Necesito ayuda con mi cuenta",
    "Gracias por la información",
    "Quiero saber cómo funciona el widget",
    "Tienen soporte por correo electrónico?",
    "Qué incluye el plan premium?",
    "Me puedes explicar la integración con WhatsApp?",
    "Solo estoy comparando opciones por ahora",
    "Hi, what services do you offer?",
    "What plans are available?",
    "Tell me about pricing and subscriptions",
    "I need help with my account login",
    "Thanks for the info",
    "How does the chat widget work?",
    "Do you offer email support?",
    "What is included in the premium plan?",
    "Can you explain the WhatsApp integration?",
    "I am only comparing options right now",
]

CHANNEL_CASES = ["twilio_whatsapp", "meta_whatsapp", "widget_chat", "email_chat"]


def _expected_lang(prompt: str) -> str:
    text = (prompt or "").lower()
    spanish_markers = [
        "¿",
        "á",
        "é",
        "í",
        "ó",
        "ú",
        "ñ",
        "hola",
        "qué",
        "quiero",
        "necesito",
        "gracias",
        "precios",
        "planes",
        "correo",
        "agendar",
        "cita",
        "reservar",
        "horario",
        "estoy",
        "comparando",
        "opciones",
        "incluye",
        "nombre",
    ]
    return "es" if any(marker in text for marker in spanish_markers) else "en"


class _FakeSupabaseQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self._filters = {}
        self._maybe_single = False

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def gte(self, key, value):
        self._filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _n):
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def execute(self):
        if self.table_name == "calendar_settings":
            data = {
                "calendar_status": "active",
                "ai_scheduling_chat_enabled": True,
                "ai_scheduling_whatsapp_enabled": True,
            }
            return SimpleNamespace(data=data if self._maybe_single else [data])

        if self.table_name == "history":
            return SimpleNamespace(data=[])

        if self.table_name == "client_settings":
            return SimpleNamespace(data=[{"session_message_limit": 24}])

        raise AssertionError(f"Unexpected table: {self.table_name}")


class _FakeSupabase:
    def table(self, table_name):
        return _FakeSupabaseQuery(table_name)


class _FakeTwilioRequest:
    def __init__(self, body, from_number):
        self._form = {"Body": body, "From": from_number}
        self.headers = {}

    async def form(self):
        return self._form


class _FakeMetaRequest:
    def __init__(self, text, business_phone="+15551234567", user_phone="15557654321"):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"display_phone_number": business_phone},
                                "messages": [
                                    {
                                        "from": user_phone,
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = {}

    async def body(self):
        return self._body


class _FakeWidgetRequest:
    def __init__(self, message):
        self._body = {
            "public_client_id": "public-client-1",
            "session_id": "widget-session-1",
            "message": message,
            "channel": "chat",
        }
        self.headers = {}
        self.client = SimpleNamespace(host="127.0.0.1")

    async def json(self):
        return self._body


@pytest.fixture
def intent_router_calendar_env(monkeypatch):
    events = []
    state_store = {}

    fake_plan_features = types.ModuleType("api.utils.plan_features_logic")
    fake_plan_features.client_has_feature = lambda _client_id, feature_key: feature_key == "calendar_sync"
    monkeypatch.setitem(sys.modules, "api.utils.plan_features_logic", fake_plan_features)

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())

    def _get_state(client_id, session_id):
        return dict(state_store.get((client_id, session_id), {}))

    def _upsert_state(client_id, session_id, state):
        state_store[(client_id, session_id)] = dict(state or {})

    async def _calendar_handler(client_id, message, session_id, channel, lang):
        return f"AGENDAR_OK|client={client_id}|channel={channel}|lang={lang}"

    def _save_history(*args, **kwargs):
        events.append({"args": args, "kwargs": kwargs})

    def _unexpected_ask_question(*_args, **_kwargs):
        raise AssertionError("ask_question should not run for direct scheduling prompts")

    monkeypatch.setattr(intent_router, "get_state", _get_state)
    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "_calendar_handler", _calendar_handler)
    monkeypatch.setattr(intent_router, "save_history", _save_history)
    monkeypatch.setattr(intent_router, "ask_question", _unexpected_ask_question)

    return {"events": events}


@pytest.fixture
def intent_router_rag_env(monkeypatch):
    events = []
    calendar_calls = []
    state_store = {}

    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase())

    def _get_state(client_id, session_id):
        return dict(state_store.get((client_id, session_id), {}))

    def _upsert_state(client_id, session_id, state):
        state_store[(client_id, session_id)] = dict(state or {})

    async def _unexpected_calendar_handler(*_args, **_kwargs):
        calendar_calls.append(True)
        raise AssertionError("calendar handler should not run for non-scheduling prompts")

    def _save_history(*args, **kwargs):
        events.append({"args": args, "kwargs": kwargs})

    def _fake_ask_question(
        messages,
        client_id,
        session_id=None,
        channel=None,
        provider=None,
        return_metadata=False,
        persist_history=True,
    ):
        last_message = (messages or [{}])[-1].get("content", "")
        lang = intent_router.detect_language(last_message)
        answer = f"RAG_OK|client={client_id}|channel={channel}|provider={provider}|lang={lang}"
        if return_metadata:
            return {
                "answer": answer,
                "confidence_score": 0.9,
                "handoff_recommended": False,
                "human_intervention_recommended": False,
                "needs_human": False,
                "handoff_reason": None,
                "confidence_reason": "test_fake_rag",
                "persist_history": persist_history,
            }
        return answer

    monkeypatch.setattr(intent_router, "get_state", _get_state)
    monkeypatch.setattr(intent_router, "upsert_state", _upsert_state)
    monkeypatch.setattr(intent_router, "_calendar_handler", _unexpected_calendar_handler)
    monkeypatch.setattr(intent_router, "save_history", _save_history)
    monkeypatch.setattr(intent_router, "ask_question", _fake_ask_question)

    return {"events": events, "calendar_calls": calendar_calls}


@pytest.fixture
def channel_wrappers_env(monkeypatch):
    sent_meta_messages = []

    # Twilio WhatsApp wrapper
    monkeypatch.setattr(twilio_webhook, "verify_twilio_signature", lambda *_a, **_k: None)
    monkeypatch.setattr(
        twilio_webhook,
        "get_client_id_by_channel",
        lambda _type, _value: "2d9987c0-a08b-41a3-bd90-1f11bf099849",
    )

    # Meta WhatsApp wrapper
    monkeypatch.setattr(meta_webhook, "verify_meta_signature", lambda *_a, **_k: None)
    monkeypatch.setattr(meta_webhook, "_is_cancel_action", lambda *_a, **_k: False)
    monkeypatch.setattr(
        meta_webhook,
        "get_client_id_by_channel",
        lambda _type, _value: "2d9987c0-a08b-41a3-bd90-1f11bf099849",
    )
    monkeypatch.setattr(
        meta_webhook,
        "get_whatsapp_credentials",
        lambda _client_id: {"wa_token": "token", "wa_phone_id": "phone-id"},
    )

    def _fake_send_whatsapp_message(**kwargs):
        sent_meta_messages.append(kwargs)

    monkeypatch.setattr(meta_webhook, "send_whatsapp_message", _fake_send_whatsapp_message)

    # Widget chat wrapper
    monkeypatch.setattr(chat_widget_api, "enforce_rate_limit", lambda **_kwargs: None)
    monkeypatch.setattr(chat_widget_api, "get_request_ip", lambda _request: "127.0.0.1")
    monkeypatch.setattr(
        chat_widget_api,
        "get_client_id_from_public_client_id",
        lambda _public_client_id: "2d9987c0-a08b-41a3-bd90-1f11bf099849",
    )
    monkeypatch.setattr(chat_widget_api, "check_and_increment_usage", lambda *_a, **_k: None)
    monkeypatch.setattr(chat_widget_api, "get_max_messages_per_session", lambda _client_id: 24)
    monkeypatch.setattr(chat_widget_api, "supabase", _FakeSupabase())

    # Email chat wrapper
    monkeypatch.setattr(chat_email, "get_client_id_from_email", lambda _email: "2d9987c0-a08b-41a3-bd90-1f11bf099849")
    monkeypatch.setattr(chat_email, "check_and_increment_usage", lambda *_a, **_k: None)
    monkeypatch.setattr(chat_email, "supabase", _FakeSupabase())
    monkeypatch.setattr(chat_email, "save_history", lambda *_a, **_k: None)

    return {"sent_meta_messages": sent_meta_messages}


def _assert_calendar_history_events(events, expected_channel, expected_provider, expected_lang):
    assert len(events) >= 2
    user_event = events[-2]
    assistant_event = events[-1]

    for event in (user_event, assistant_event):
        kwargs = event["kwargs"]
        assert kwargs.get("channel") == expected_channel
        assert kwargs.get("provider") == expected_provider
        assert kwargs.get("source_type") == "appointment"

    answer = assistant_event["args"][3]
    assert answer.startswith("AGENDAR_OK|")
    assert f"|lang={expected_lang}" in answer


def _assert_not_scheduled(events, calendar_calls):
    assert not calendar_calls
    for event in events:
        kwargs = event.get("kwargs", {})
        assert kwargs.get("source_type") != "appointment"
        args = event.get("args", ())
        if len(args) > 3 and isinstance(args[3], str):
            assert not args[3].startswith("AGENDAR_OK|")


async def _run_twilio(prompt):
    req = _FakeTwilioRequest(body=prompt, from_number="whatsapp:+15557654321")
    return await twilio_webhook.twilio_webhook(req, Body=prompt, From="whatsapp:+15557654321")


async def _run_meta(prompt):
    req = _FakeMetaRequest(text=prompt)
    return await meta_webhook.receive_whatsapp_message(req)


async def _run_widget(prompt):
    req = _FakeWidgetRequest(message=prompt)
    return await chat_widget_api.chat_widget(req)


async def _run_email(prompt):
    return await chat_email.process_chat_email_payload(
        {
            "from_email": "assistant@example.com",
            "subject": "Agenda",
            "message": prompt,
        }
    )


@pytest.mark.parametrize("channel_case", CHANNEL_CASES)
@pytest.mark.parametrize("prompt", DIRECT_SCHEDULING_PROMPTS)
def test_direct_scheduling_user_flows_return_calendar_response(
    prompt,
    channel_case,
    intent_router_calendar_env,
    channel_wrappers_env,
):
    events = intent_router_calendar_env["events"]
    expected_lang = _expected_lang(prompt)

    if channel_case == "twilio_whatsapp":
        response = asyncio.run(_run_twilio(prompt))
        body = response.body.decode("utf-8")
        assert "AGENDAR_OK|" in body
        assert f"|lang={expected_lang}" in body
        _assert_calendar_history_events(
            events,
            expected_channel="whatsapp",
            expected_provider="twilio",
            expected_lang=expected_lang,
        )
        return

    if channel_case == "meta_whatsapp":
        response = asyncio.run(_run_meta(prompt))
        payload = json.loads(response.body.decode("utf-8"))
        assert payload["status"] == "ok"
        assert channel_wrappers_env["sent_meta_messages"]
        last_sent = channel_wrappers_env["sent_meta_messages"][-1]
        assert "AGENDAR_OK|" in last_sent["message"]
        assert f"|lang={expected_lang}" in last_sent["message"]
        _assert_calendar_history_events(
            events,
            expected_channel="whatsapp",
            expected_provider="meta",
            expected_lang=expected_lang,
        )
        return

    if channel_case == "widget_chat":
        response = asyncio.run(_run_widget(prompt))
        assert response["session_id"] == "widget-session-1"
        assert response["answer"].startswith("AGENDAR_OK|")
        assert f"|lang={expected_lang}" in response["answer"]
        _assert_calendar_history_events(
            events,
            expected_channel="chat",
            expected_provider="widget",
            expected_lang=expected_lang,
        )
        return

    if channel_case == "email_chat":
        response = asyncio.run(_run_email(prompt))
        assert response["channel"] == "email"
        assert response["answer"].startswith("AGENDAR_OK|")
        assert f"|lang={expected_lang}" in response["answer"]
        _assert_calendar_history_events(
            events,
            expected_channel="email",
            expected_provider="gmail",
            expected_lang=expected_lang,
        )
        return

    raise AssertionError(f"Unknown channel_case: {channel_case}")


@pytest.mark.parametrize("channel_case", CHANNEL_CASES)
@pytest.mark.parametrize("prompt", NON_SCHEDULING_PROMPTS)
def test_non_scheduling_conversations_do_not_trigger_calendar(
    prompt,
    channel_case,
    intent_router_rag_env,
    channel_wrappers_env,
):
    events = intent_router_rag_env["events"]
    calendar_calls = intent_router_rag_env["calendar_calls"]
    expected_lang = _expected_lang(prompt)

    if channel_case == "twilio_whatsapp":
        response = asyncio.run(_run_twilio(prompt))
        body = response.body.decode("utf-8")
        assert "RAG_OK|" in body
        assert f"|lang={expected_lang}" in body
        _assert_not_scheduled(events, calendar_calls)
        return

    if channel_case == "meta_whatsapp":
        response = asyncio.run(_run_meta(prompt))
        payload = json.loads(response.body.decode("utf-8"))
        assert payload["status"] == "ok"
        assert channel_wrappers_env["sent_meta_messages"]
        last_sent = channel_wrappers_env["sent_meta_messages"][-1]
        assert "RAG_OK|" in last_sent["message"]
        assert f"|lang={expected_lang}" in last_sent["message"]
        _assert_not_scheduled(events, calendar_calls)
        return

    if channel_case == "widget_chat":
        response = asyncio.run(_run_widget(prompt))
        assert response["session_id"] == "widget-session-1"
        assert response["answer"].startswith("RAG_OK|")
        assert f"|lang={expected_lang}" in response["answer"]
        _assert_not_scheduled(events, calendar_calls)
        return

    if channel_case == "email_chat":
        response = asyncio.run(_run_email(prompt))
        assert response["channel"] == "email"
        assert response["answer"].startswith("RAG_OK|")
        assert f"|lang={expected_lang}" in response["answer"]
        _assert_not_scheduled(events, calendar_calls)
        return

    raise AssertionError(f"Unknown channel_case: {channel_case}")
