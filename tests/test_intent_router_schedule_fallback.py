import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag import intent_router


def test_schedule_intent_uses_keyword_fallback_when_advanced_detector_returns_false(monkeypatch):
    monkeypatch.setattr(intent_router, "_detect_intent_to_schedule", lambda _msg: False)
    assert intent_router.detect_intent_to_schedule("me ayudas a reservar una cita")


def test_schedule_intent_keeps_false_when_no_signals(monkeypatch):
    monkeypatch.setattr(intent_router, "_detect_intent_to_schedule", lambda _msg: False)
    assert not intent_router.detect_intent_to_schedule("solo estoy comparando precios")
