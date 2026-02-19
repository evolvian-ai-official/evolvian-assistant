from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_DSAR_RESPONSE_DAYS = 45
MAX_DSAR_EXTENSION_DAYS = 45
DSAR_META_MARKER = "\n\n[EVOLVIAN_DSAR_META]\n"
DSAR_META_MARKER_INLINE = "[EVOLVIAN_DSAR_META]\n"

DSAR_REQUEST_TYPES = {
    "access",
    "delete",
    "correct",
    "opt_out_sale_share",
    "marketing_opt_out",
}

DSAR_STATUSES = {
    "pending",
    "verification_required",
    "verified",
    "in_progress",
    "fulfilled",
    "denied",
    "withdrawn",
}

ALLOWED_STATUS_TRANSITIONS = {
    "pending": {
        "verification_required",
        "verified",
        "in_progress",
        "denied",
        "withdrawn",
    },
    "verification_required": {"verified", "denied", "withdrawn"},
    "verified": {"in_progress", "denied", "withdrawn"},
    "in_progress": {"fulfilled", "denied", "withdrawn"},
    "fulfilled": set(),
    "denied": set(),
    "withdrawn": set(),
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def calculate_due_at(submitted_at: datetime, extension_days: int = 0) -> datetime:
    if extension_days < 0 or extension_days > MAX_DSAR_EXTENSION_DAYS:
        raise ValueError("extension_days_out_of_range")
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    return submitted_at.astimezone(timezone.utc) + timedelta(
        days=DEFAULT_DSAR_RESPONSE_DAYS + extension_days
    )


def normalize_status(status: str | None) -> str:
    value = (status or "pending").strip().lower()
    return value if value in DSAR_STATUSES else "pending"


def normalize_request_type(request_type: str | None) -> str:
    value = (request_type or "").strip().lower()
    if value not in DSAR_REQUEST_TYPES:
        raise ValueError("invalid_request_type")
    return value


def is_valid_status_transition(current_status: str, next_status: str) -> bool:
    current = normalize_status(current_status)
    next_value = normalize_status(next_status)
    if current == next_value:
        return True
    return next_value in ALLOWED_STATUS_TRANSITIONS.get(current, set())


def _as_json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def split_details_and_metadata(details: str | None) -> tuple[str, dict[str, Any]]:
    raw = (details or "").strip()
    if not raw:
        return "", {}

    if DSAR_META_MARKER in raw:
        message, _, meta_part = raw.rpartition(DSAR_META_MARKER)
        metadata = _as_json_obj(meta_part.strip())
        return message.strip(), metadata

    if raw.startswith(DSAR_META_MARKER_INLINE):
        _, _, meta_part = raw.partition(DSAR_META_MARKER_INLINE)
        metadata = _as_json_obj(meta_part.strip())
        return "", metadata

    if DSAR_META_MARKER_INLINE not in raw:
        return raw, {}

    message, _, meta_part = raw.rpartition(DSAR_META_MARKER_INLINE)
    metadata = _as_json_obj(meta_part.strip())
    return message.strip(), metadata


def combine_details_and_metadata(details: str, metadata: dict[str, Any]) -> str:
    text = (details or "").strip()
    if not metadata:
        return text
    packed = json.dumps(metadata, separators=(",", ":"), ensure_ascii=True)
    if text:
        return f"{text}{DSAR_META_MARKER}{packed}"
    return f"{DSAR_META_MARKER_INLINE}{packed}"


def append_event(
    metadata: dict[str, Any],
    *,
    action: str,
    actor: str,
    note: str | None = None,
    at: datetime | None = None,
) -> dict[str, Any]:
    enriched = deepcopy(metadata) if isinstance(metadata, dict) else {}
    events = enriched.get("events")
    if not isinstance(events, list):
        events = []
    event = {
        "at": isoformat_utc(at or now_utc()),
        "action": action,
        "actor": actor,
    }
    if note:
        event["note"] = note.strip()[:500]
    events.append(event)
    enriched["events"] = events
    return enriched


def build_initial_metadata(
    *,
    request_id: str,
    request_type: str,
    submitted_at: datetime,
    due_at: datetime,
    source: str,
) -> dict[str, Any]:
    metadata = {
        "request_id": request_id,
        "request_type": normalize_request_type(request_type),
        "status": "pending",
        "submitted_at": isoformat_utc(submitted_at),
        "due_at": isoformat_utc(due_at),
        "extension_days": 0,
        "verification_status": "pending",
        "source": source,
    }
    return append_event(
        metadata,
        action="submitted",
        actor="requester",
        at=submitted_at,
    )


def ensure_request_metadata(
    *,
    record: dict[str, Any],
    request_id: str,
) -> tuple[str, dict[str, Any]]:
    details_text, metadata = split_details_and_metadata(record.get("details"))
    if metadata:
        return details_text, metadata

    created_at = parse_iso_datetime(record.get("created_at")) or now_utc()
    due_at = calculate_due_at(created_at)
    request_type = str(record.get("request_type") or "access")
    if request_type not in DSAR_REQUEST_TYPES:
        request_type = "access"

    seeded = build_initial_metadata(
        request_id=request_id,
        request_type=request_type,
        submitted_at=created_at,
        due_at=due_at,
        source=str(record.get("source") or "unknown"),
    )
    seeded["status"] = normalize_status(str(record.get("status") or "pending"))
    return details_text, seeded


def get_due_at_from_metadata(metadata: dict[str, Any], *, created_at: str | None) -> datetime:
    due_at = parse_iso_datetime(str(metadata.get("due_at") or ""))
    if due_at:
        return due_at
    created = parse_iso_datetime(created_at) or now_utc()
    return calculate_due_at(created)


def is_overdue(metadata: dict[str, Any], *, created_at: str | None, now: datetime | None = None) -> bool:
    current = now or now_utc()
    due_at = get_due_at_from_metadata(metadata, created_at=created_at)
    status = normalize_status(str(metadata.get("status") or "pending"))
    if status in {"fulfilled", "denied", "withdrawn"}:
        return False
    return current > due_at
