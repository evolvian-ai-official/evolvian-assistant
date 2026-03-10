import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import calendar_intent_handler as module


COMMON_SETTINGS = {
    "timezone": "America/Mexico_City",
    "calendar_status": "active",
    "slot_duration_minutes": 45,
    "buffer_minutes": 0,
    "min_notice_hours": 0,
    "max_days_ahead": 10,
    "allow_same_day": True,
    "start_time": "09:00",
    "end_time": "18:00",
    "selected_days": ["mon", "tue", "wed", "thu", "fri"],
}


def _history_row(role: str, content: str, idx: int) -> dict:
    created_at = datetime.now(timezone.utc) - timedelta(minutes=(100 - idx))
    return {
        "role": role,
        "content": content,
        "source_type": "appointment",
        "channel": "whatsapp",
        "created_at": created_at.isoformat(),
    }


class _FakeQuery:
    def __init__(self, table_name: str, data_source: dict):
        self.table_name = table_name
        self.data_source = data_source
        self._state_for_upsert = None
        self._order_desc = False

    def select(self, _fields):
        return self

    def eq(self, _key, _value):
        return self

    def order(self, _column, desc=False):
        self._order_desc = bool(desc)
        return self

    def limit(self, _n):
        return self

    def upsert(self, payload, on_conflict=None):  # noqa: ARG002
        self._state_for_upsert = payload
        return self

    def execute(self):
        if self.table_name == "conversation_state":
            if self._state_for_upsert:
                self.data_source["conversation_state"] = self._state_for_upsert.get("state") or {}
                return SimpleNamespace(data=[{"state": self.data_source["conversation_state"]}])
            state = self.data_source.get("conversation_state")
            if not state:
                return SimpleNamespace(data=[])
            return SimpleNamespace(data=[{"state": state}])

        if self.table_name == "history":
            rows = list(self.data_source.get("history_rows") or [])
            if self._order_desc:
                rows = list(reversed(rows))
            return SimpleNamespace(data=rows)

        raise AssertionError(f"Unexpected table query: {self.table_name}")


class _FakeSupabase:
    def __init__(self, data_source: dict):
        self.data_source = data_source

    def table(self, name):
        return _FakeQuery(name, self.data_source)


def _setup_calendar_handler(monkeypatch, history_rows, *, allow_slot_generation=False):
    data_source = {
        "conversation_state": {},
        "history_rows": history_rows,
    }
    monkeypatch.setattr(module, "supabase", _FakeSupabase(data_source))
    monkeypatch.setattr(module, "_load_settings", lambda _client_id: dict(COMMON_SETTINGS))
    if allow_slot_generation:
        monkeypatch.setattr(
            module,
            "_generate_available_slots",
            lambda *_a, **_k: [
                {"start_iso": "2026-03-10T15:00:00-06:00", "readable": "2026-03-10 15:00"},
                {"start_iso": "2026-03-10T15:45:00-06:00", "readable": "2026-03-10 15:45"},
            ],
        )
    else:
        monkeypatch.setattr(
            module,
            "_generate_available_slots",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("slot generation should not run after recovery")),
        )
    monkeypatch.setattr(
        module,
        "openai_chat",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("LLM should not run in backend collecting flow")),
    )


def test_state_recovery_slot_selection_continues_to_name(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="mañana a las 3PM",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "¿Cuál es tu nombre completo?" in answer


def test_state_recovery_date_then_time_split_keeps_progress(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
        _history_row("user", "mañana", 12),
        _history_row("assistant", "Perfecto, ¿a qué hora te gustaría?", 13),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="a las 3PM",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "¿Cuál es tu nombre completo?" in answer


def test_state_recovery_name_step_continues_to_email(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
        _history_row("user", "mañana a las 3PM", 12),
        _history_row("assistant", "Perfecto. ¿Cuál es tu nombre completo?", 13),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="Aldo Benitez",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="en",
        )
    )

    assert "¿Cuál es tu correo electrónico?" in answer


def test_state_recovery_email_step_continues_to_phone(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
        _history_row("user", "mañana a las 3PM", 12),
        _history_row("assistant", "Perfecto. ¿Cuál es tu nombre completo?", 13),
        _history_row("user", "Aldo Benitez", 14),
        _history_row("assistant", "Gracias. ¿Cuál es tu correo electrónico?", 15),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="aldo.benitez@example.com",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "¿Cuál es tu número de teléfono" in answer


def test_state_recovery_phone_step_continues_to_confirmation(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
        _history_row("user", "mañana a las 3PM", 12),
        _history_row("assistant", "Perfecto. ¿Cuál es tu nombre completo?", 13),
        _history_row("user", "Aldo Benitez", 14),
        _history_row("assistant", "Gracias. ¿Cuál es tu correo electrónico?", 15),
        _history_row("user", "aldo.benitez@example.com", 16),
        _history_row("assistant", "Gracias. ¿Cuál es tu número de teléfono con WhatsApp?", 17),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="+525512345678",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "¿Confirmas la cita?" in answer


def test_state_recovery_confirmation_step_closes_booking(monkeypatch):
    history_rows = [
        _history_row("user", "Quiero agendar una cita", 10),
        _history_row("assistant", "Indícame cuál prefieres.", 11),
        _history_row("user", "mañana a las 3PM", 12),
        _history_row("assistant", "Perfecto. ¿Cuál es tu nombre completo?", 13),
        _history_row("user", "Aldo Benitez", 14),
        _history_row("assistant", "Gracias. ¿Cuál es tu correo electrónico?", 15),
        _history_row("user", "aldo.benitez@example.com", 16),
        _history_row("assistant", "Gracias. ¿Cuál es tu número de teléfono con WhatsApp?", 17),
        _history_row("user", "+525512345678", 18),
        _history_row("assistant", "¿Confirmas la cita? (responde: Sí o No)", 19),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    booking_calls = []

    async def _fake_book(_client_id, _session_id, _collected, _channel):
        booking_calls.append(True)
        return {"ok": True}

    monkeypatch.setattr(module, "_book_appointment", _fake_book)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="Confirmo la cita",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "Tu cita ha sido registrada" in answer
    assert booking_calls, "booking flow should close on confirmation"


def test_explicit_restart_ignores_stale_history_and_starts_from_slots(monkeypatch):
    stale_history = [
        {
            "role": "user",
            "content": "I want to book an appointment",
            "source_type": "appointment",
            "channel": "whatsapp",
            "created_at": "2026-03-06T19:10:00Z",
        },
        {
            "role": "assistant",
            "content": "Thanks. What is your email address?",
            "source_type": "appointment",
            "channel": "whatsapp",
            "created_at": "2026-03-06T19:11:00Z",
        },
    ]
    _setup_calendar_handler(monkeypatch, stale_history, allow_slot_generation=True)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="quiero agendar",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="es",
        )
    )

    assert "Con gusto te ayudo a agendar tu cita" in answer
    assert "Indícame cuál prefieres" in answer
    assert "Thanks." not in answer


def test_recovery_keeps_spanish_and_does_not_loop_back_to_email_after_phone(monkeypatch):
    history_rows = [
        _history_row("user", "quiero agendar", 30),
        _history_row("assistant", "Con gusto te ayudo a agendar tu cita. Indícame cuál prefieres.", 31),
        _history_row("user", "mañana a las 3PM", 32),
        _history_row("assistant", "Perfecto. ¿Cuál es tu nombre completo?", 33),
        _history_row("user", "Aldo Benitez", 34),
        _history_row("assistant", "Gracias. ¿Cuál es tu correo electrónico?", 35),
        _history_row("user", "aldo.benitez.cortes@gmail.com", 36),
        _history_row("assistant", "Gracias. ¿Cuál es tu número de teléfono con WhatsApp?", 37),
    ]
    _setup_calendar_handler(monkeypatch, history_rows)

    answer = asyncio.run(
        module.handle_calendar_intent(
            client_id="client-1",
            message="+52552527760",
            session_id="whatsapp-5215512345678",
            channel="whatsapp",
            lang="en",
        )
    )

    assert "¿Confirmas la cita?" in answer
    assert "What is your email address?" not in answer
