from datetime import datetime, timezone

from api.compliance.retention_policy import (
    RETENTION_APPLY_ENV,
    compute_cutoff,
    get_rule_map,
    is_retention_apply_allowed,
    normalize_table_selection,
    rule_to_dict,
)


def test_retention_rules_include_core_tables():
    rules = get_rule_map()
    assert "history" in rules
    assert "widget_consents" in rules
    assert rules["history"].action in {"delete", "anonymize"}


def test_compute_cutoff_uses_utc_and_days():
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    cutoff = compute_cutoff(now, 30)
    assert cutoff.isoformat() == "2026-01-20T12:00:00+00:00"


def test_normalize_table_selection_filters_unknown():
    selected = normalize_table_selection(["history", "unknown_table", "history", "widget_consents"])
    assert selected == ["history", "widget_consents"]


def test_apply_flag_guard(monkeypatch):
    monkeypatch.delenv(RETENTION_APPLY_ENV, raising=False)
    assert is_retention_apply_allowed() is False

    monkeypatch.setenv(RETENTION_APPLY_ENV, "true")
    assert is_retention_apply_allowed() is True


def test_rule_to_dict_includes_cutoff():
    rule = get_rule_map()["history"]
    payload = rule_to_dict(rule, now=datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc))
    assert payload["table"] == "history"
    assert "cutoff_at" in payload
