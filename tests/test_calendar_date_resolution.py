import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import calendar_intent_handler as module


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 3, 9, 21, 11, 0)
        if tz is not None:
            return base.replace(tzinfo=tz)
        return base


def test_explicit_spanish_date_takes_priority_over_next_weekday(monkeypatch):
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    resolved = module._resolve_date_token("Me gustaría agendar el proximo Jueves 12 de marzo a las 12pM")

    assert resolved == "2026-03-12"


def test_explicit_numeric_date_takes_priority_over_next_weekday(monkeypatch):
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    resolved = module._resolve_date_token("próximo jueves 12/03 a las 12")

    assert resolved == "2026-03-12"


def test_next_weekday_without_explicit_date_means_immediate_upcoming_weekday(monkeypatch):
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    resolved = module._resolve_date_token("próximo jueves")

    assert resolved == "2026-03-12"


def test_explicit_next_week_marker_pushes_one_week(monkeypatch):
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    resolved = module._resolve_date_token("jueves de la próxima semana")

    assert resolved == "2026-03-19"
