import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import intent_router


def _history_row(content: str, *, minutes_ago: int = 1, source_type: str = "appointment") -> dict:
    return {
        "source_type": source_type,
        "channel": "whatsapp",
        "content": content,
        "created_at": (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(),
    }


class _HistoryQuery:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def select(self, _fields):
        return self

    def eq(self, _key, _value):
        return self

    def order(self, _col, desc=False):  # noqa: ARG002
        return self

    def limit(self, _n):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _FakeSupabase:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def table(self, name: str):
        if name != "history":
            raise AssertionError(f"Unexpected table: {name}")
        return _HistoryQuery(self.rows)


def test_recent_history_does_not_recover_calendar_after_booking_confirmation(monkeypatch):
    rows = [
        _history_row("✅ Tu cita ha sido registrada. (Recibirás confirmación pronto.)"),
        _history_row("Hola Aldo 👋 Le escribe Evolvian LLC para recordarle su próxima cita."),
    ]
    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase(rows))

    recovered = intent_router._has_recent_appointment_history(
        client_id="client-1",
        session_id="session-1",
        channel="whatsapp",
    )

    assert recovered is False


def test_recent_history_recovers_calendar_when_flow_is_in_progress(monkeypatch):
    rows = [
        _history_row("Perfecto. ¿Cuál es tu nombre completo?"),
        _history_row("Indícame cuál prefieres."),
    ]
    monkeypatch.setattr(intent_router, "supabase", _FakeSupabase(rows))

    recovered = intent_router._has_recent_appointment_history(
        client_id="client-2",
        session_id="session-2",
        channel="whatsapp",
    )

    assert recovered is True


def test_calendar_followup_ignores_non_name_product_phrases():
    assert intent_router._looks_like_calendar_followup("Instalar Instagram") is False
    assert intent_router._looks_like_calendar_followup("Aldo Benitez") is True
