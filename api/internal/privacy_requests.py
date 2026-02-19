from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.config.config import supabase
from api.internal_auth import require_internal_request
from api.privacy_dsr import (
    DSAR_REQUEST_TYPES,
    DSAR_STATUSES,
    append_event,
    calculate_due_at,
    combine_details_and_metadata,
    ensure_request_metadata,
    get_due_at_from_metadata,
    is_overdue,
    is_valid_status_transition,
    isoformat_utc,
    normalize_status,
    now_utc,
    parse_iso_datetime,
    split_details_and_metadata,
)


router = APIRouter(prefix="/api/internal/privacy", tags=["Privacy DSAR Internal"])
PRIVACY_REQUEST_TABLE = "public_privacy_requests"
TERMINAL_STATUSES = {"fulfilled", "denied", "withdrawn"}
VALID_VERIFICATION_STATUSES = {"pending", "verified", "failed", "not_required"}


class PrivacyRequestUpdatePayload(BaseModel):
    status: str | None = Field(default=None)
    verification_status: str | None = Field(default=None)
    note: str = Field(default="", max_length=1200)
    extension_days: int | None = Field(default=None, ge=0, le=45)


def _fallback_request_id_from_row(row_id: str) -> str:
    compact = row_id.replace("-", "").lower()
    return f"dsar_{compact[:12]}"


def _normalize_request_id(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized.startswith("dsar_"):
        raise HTTPException(status_code=400, detail="invalid_request_id")
    return normalized


def _row_to_record(row: Any) -> dict[str, Any]:
    return row if isinstance(row, dict) else {}


def _load_request_rows(*, limit: int, offset: int = 0) -> list[dict[str, Any]]:
    response = (
        supabase.table(PRIVACY_REQUEST_TABLE)
        .select(
            "id,name,email,request_type,status,language,source,details,created_at,user_agent,ip_address"
        )
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [_row_to_record(row) for row in (response.data or [])]


def _find_request_by_request_id(request_id: str, *, max_scan: int = 10000) -> tuple[dict[str, Any], dict[str, Any], str]:
    scanned = 0
    offset = 0
    batch = 200

    while scanned < max_scan:
        rows = _load_request_rows(limit=batch, offset=offset)
        if not rows:
            break

        for row in rows:
            row_id = str(row.get("id") or "")
            fallback_request_id = _fallback_request_id_from_row(row_id) if row_id else request_id
            _, metadata = ensure_request_metadata(record=row, request_id=fallback_request_id)
            if str(metadata.get("request_id") or "").strip().lower() == request_id:
                return row, metadata, fallback_request_id

        scanned += len(rows)
        offset += batch

    raise HTTPException(status_code=404, detail="privacy_request_not_found")


def _serialize_row(row: dict[str, Any], metadata: dict[str, Any], fallback_request_id: str) -> dict[str, Any]:
    due_at = get_due_at_from_metadata(metadata, created_at=row.get("created_at"))
    status = normalize_status(str(metadata.get("status") or row.get("status") or "pending"))
    return {
        "request_id": metadata.get("request_id") or fallback_request_id,
        "row_id": row.get("id"),
        "email": row.get("email"),
        "name": row.get("name"),
        "request_type": metadata.get("request_type") or row.get("request_type"),
        "status": status,
        "verification_status": metadata.get("verification_status", "pending"),
        "source": row.get("source"),
        "submitted_at": metadata.get("submitted_at") or row.get("created_at"),
        "due_at": isoformat_utc(due_at),
        "extension_days": int(metadata.get("extension_days") or 0),
        "overdue": is_overdue(metadata, created_at=row.get("created_at")),
    }


@router.get("/requests")
def list_privacy_requests(
    request: Request,
    status: str | None = Query(default=None),
    request_type: str | None = Query(default=None),
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
):
    require_internal_request(request)
    expected_status = None
    if status:
        candidate = status.strip().lower()
        if candidate not in DSAR_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status_filter")
        expected_status = candidate

    expected_type = None
    if request_type:
        candidate_type = request_type.strip().lower()
        if candidate_type not in DSAR_REQUEST_TYPES:
            raise HTTPException(status_code=400, detail="invalid_request_type_filter")
        expected_type = candidate_type

    rows = _load_request_rows(limit=limit, offset=offset)
    items: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("id") or "")
        fallback_request_id = _fallback_request_id_from_row(row_id) if row_id else ""
        _, metadata = ensure_request_metadata(record=row, request_id=fallback_request_id)
        serialized = _serialize_row(row, metadata, fallback_request_id)

        if expected_status and serialized["status"] != expected_status:
            continue
        if expected_type and str(serialized["request_type"] or "").strip().lower() != expected_type:
            continue
        if overdue_only and not serialized["overdue"]:
            continue
        items.append(serialized)

    return {
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.patch("/requests/{request_id}")
def update_privacy_request(
    request_id: str,
    payload: PrivacyRequestUpdatePayload,
    request: Request,
):
    require_internal_request(request)
    normalized_request_id = _normalize_request_id(request_id)

    if payload.status and payload.status.strip().lower() not in DSAR_STATUSES:
        raise HTTPException(status_code=400, detail="invalid_status")
    if payload.verification_status and payload.verification_status.strip().lower() not in VALID_VERIFICATION_STATUSES:
        raise HTTPException(status_code=400, detail="invalid_verification_status")

    row, metadata, fallback_request_id = _find_request_by_request_id(normalized_request_id)
    details_text, _ = split_details_and_metadata(row.get("details"))
    mutable = deepcopy(metadata)

    actor = "internal_operator"
    update_note = payload.note.strip()
    now = now_utc()

    current_status = normalize_status(str(mutable.get("status") or row.get("status") or "pending"))
    next_status = current_status
    if payload.status:
        next_status = normalize_status(payload.status)
        if not is_valid_status_transition(current_status, next_status):
            raise HTTPException(
                status_code=409,
                detail=f"invalid_status_transition:{current_status}->{next_status}",
            )
        mutable["status"] = next_status

    if payload.verification_status:
        mutable["verification_status"] = payload.verification_status.strip().lower()

    if payload.extension_days is not None:
        submitted_at = parse_iso_datetime(str(mutable.get("submitted_at") or "")) or parse_iso_datetime(
            row.get("created_at")
        )
        submitted_at = submitted_at or now
        due_at = calculate_due_at(submitted_at, payload.extension_days)
        mutable["extension_days"] = payload.extension_days
        mutable["due_at"] = isoformat_utc(due_at)

    if next_status in TERMINAL_STATUSES:
        mutable["closed_at"] = isoformat_utc(now)

    event_note_parts: list[str] = []
    if payload.status:
        event_note_parts.append(f"status={current_status}->{next_status}")
    if payload.verification_status:
        event_note_parts.append(f"verification={payload.verification_status.strip().lower()}")
    if payload.extension_days is not None:
        event_note_parts.append(f"extension_days={payload.extension_days}")
    if update_note:
        event_note_parts.append(update_note[:500])
    event_note = " | ".join(event_note_parts) if event_note_parts else None

    mutable = append_event(
        mutable,
        action="internal_update",
        actor=actor,
        note=event_note,
        at=now,
    )

    updated_status = normalize_status(str(mutable.get("status") or next_status))
    details_with_metadata = combine_details_and_metadata(details_text, mutable)
    update_payload = {
        "status": updated_status,
        "details": details_with_metadata,
    }

    try:
        (
            supabase.table(PRIVACY_REQUEST_TABLE)
            .update(update_payload)
            .eq("id", row.get("id"))
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"privacy_request_update_failed: {error}") from error

    serialized = _serialize_row(row, mutable, fallback_request_id)
    return {
        "updated": True,
        "request": serialized,
    }


@router.get("/metrics")
def get_privacy_request_metrics(
    request: Request,
    max_rows: int = Query(default=2000, ge=100, le=10000),
):
    require_internal_request(request)

    scanned = 0
    offset = 0
    batch = 200
    now = now_utc()

    open_count = 0
    overdue_open_count = 0
    closed_count = 0
    closed_on_time_count = 0
    status_counts: dict[str, int] = {}

    while scanned < max_rows:
        rows = _load_request_rows(limit=batch, offset=offset)
        if not rows:
            break

        for row in rows:
            row_id = str(row.get("id") or "")
            fallback_request_id = _fallback_request_id_from_row(row_id) if row_id else ""
            _, metadata = ensure_request_metadata(record=row, request_id=fallback_request_id)
            status = normalize_status(str(metadata.get("status") or row.get("status") or "pending"))
            status_counts[status] = status_counts.get(status, 0) + 1

            due_at = get_due_at_from_metadata(metadata, created_at=row.get("created_at"))
            if status in TERMINAL_STATUSES:
                closed_count += 1
                closed_at = parse_iso_datetime(str(metadata.get("closed_at") or "")) or parse_iso_datetime(
                    row.get("created_at")
                )
                if closed_at and closed_at <= due_at:
                    closed_on_time_count += 1
            else:
                open_count += 1
                if is_overdue(metadata, created_at=row.get("created_at"), now=now):
                    overdue_open_count += 1

        scanned += len(rows)
        offset += batch

    on_time_rate = (
        round((closed_on_time_count / closed_count) * 100, 2)
        if closed_count > 0
        else None
    )

    return {
        "scanned": scanned,
        "open_count": open_count,
        "overdue_open_count": overdue_open_count,
        "closed_count": closed_count,
        "closed_on_time_count": closed_on_time_count,
        "closed_on_time_rate_pct": on_time_rate,
        "status_counts": status_counts,
        "snapshot_at": isoformat_utc(now),
    }
