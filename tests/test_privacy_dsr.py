from datetime import datetime, timedelta, timezone

from api.privacy_dsr import (
    build_initial_metadata,
    calculate_due_at,
    combine_details_and_metadata,
    is_overdue,
    is_valid_status_transition,
    split_details_and_metadata,
)


def test_calculate_due_at_defaults_to_45_days():
    submitted_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    due_at = calculate_due_at(submitted_at)
    assert due_at == submitted_at + timedelta(days=45)


def test_status_transition_rules():
    assert is_valid_status_transition("pending", "in_progress") is True
    assert is_valid_status_transition("in_progress", "fulfilled") is True
    assert is_valid_status_transition("fulfilled", "in_progress") is False


def test_details_metadata_roundtrip():
    submitted_at = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
    due_at = calculate_due_at(submitted_at)
    metadata = build_initial_metadata(
        request_id="dsar_abc123def456",
        request_type="access",
        submitted_at=submitted_at,
        due_at=due_at,
        source="public_page",
    )

    packed = combine_details_and_metadata("Please export my data", metadata)
    details, unpacked = split_details_and_metadata(packed)

    assert details == "Please export my data"
    assert unpacked["request_id"] == "dsar_abc123def456"
    assert unpacked["status"] == "pending"


def test_is_overdue_uses_due_at_and_terminal_state():
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    active_metadata = {
        "status": "in_progress",
        "due_at": "2026-02-10T00:00:00+00:00",
    }
    closed_metadata = {
        "status": "fulfilled",
        "due_at": "2026-02-10T00:00:00+00:00",
    }

    assert is_overdue(active_metadata, created_at=None, now=now) is True
    assert is_overdue(closed_metadata, created_at=None, now=now) is False
