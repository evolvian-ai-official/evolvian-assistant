from datetime import datetime, timezone

from api import terms_api


def test_terms_valid_days_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("TERMS_ACCEPTANCE_VALID_DAYS", raising=False)
    assert terms_api._terms_valid_days() == 0


def test_terms_valid_days_parses_positive_int(monkeypatch):
    monkeypatch.setenv("TERMS_ACCEPTANCE_VALID_DAYS", "45")
    assert terms_api._terms_valid_days() == 45


def test_terms_valid_days_rejects_invalid(monkeypatch):
    monkeypatch.setenv("TERMS_ACCEPTANCE_VALID_DAYS", "abc")
    assert terms_api._terms_valid_days() == 0


def test_parse_accepted_at_handles_iso_with_z():
    parsed = terms_api._parse_accepted_at("2026-02-19T13:00:00Z")
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo == timezone.utc


def test_parse_accepted_at_returns_none_for_bad_value():
    assert terms_api._parse_accepted_at("not-a-date") is None
