from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.config.config import supabase
from api.internal.audit_document_index_health import audit_document_index_health
from api.internal.reindex_single_client import reindex_client
from api.internal_auth import require_internal_request
from api.utils.paths import (
    get_base_data_path,
    get_render_persistent_mount_path,
    is_running_on_render,
)


router = APIRouter(
    prefix="/api/internal/indexing",
    tags=["Indexing Internal"],
)

FAILED_CLIENT_COOLDOWN_MINUTES = int(
    os.getenv("EVOLVIAN_REINDEX_FAILURE_COOLDOWN_MINUTES") or "30"
)
LOCK_STALE_AFTER_MINUTES = int(
    os.getenv("EVOLVIAN_REINDEX_LOCK_STALE_MINUTES") or "15"
)


class ReindexBatchPayload(BaseModel):
    client_ids: list[str] | None = None
    max_clients: int = Field(default=1, ge=1, le=25)
    only_at_risk: bool = True


def _runtime_context() -> dict:
    base_data_path = get_base_data_path()
    render_disk_mount = get_render_persistent_mount_path()
    return {
        "base_data_path": base_data_path,
        "render_disk_configured": bool(render_disk_mount),
        "render_disk_mount_path": render_disk_mount or None,
        "running_on_render": is_running_on_render(),
        "effective_data_path_is_persistent": bool(render_disk_mount) and (
            Path(base_data_path).resolve() == Path(render_disk_mount).resolve()
        ),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _failure_state_path() -> Path:
    return Path(get_base_data_path()) / ".reindex-failures.json"


def _load_failure_state() -> dict[str, dict]:
    path = _failure_state_path()
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _save_failure_state(state: dict[str, dict]) -> None:
    path = _failure_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=True, indent=2, sort_keys=True)
    tmp_path.replace(path)


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _filter_retryable_client_ids(client_ids: list[str]) -> tuple[list[str], list[str]]:
    state = _load_failure_state()
    if not state:
        return client_ids, []

    now = _utcnow()
    cooldown = timedelta(minutes=FAILED_CLIENT_COOLDOWN_MINUTES)
    selected: list[str] = []
    skipped: list[str] = []

    for client_id in client_ids:
        entry = state.get(client_id) or {}
        failed_at = _parse_iso_timestamp(entry.get("last_failed_at"))
        if failed_at and now - failed_at < cooldown:
            skipped.append(client_id)
            continue
        selected.append(client_id)

    return selected, skipped


def _remember_reindex_results(results: list[dict]) -> None:
    state = _load_failure_state()
    changed = False

    for result in results:
        client_id = str(result.get("client_id") or "").strip()
        if not client_id:
            continue

        if result.get("status") == "partial_failure":
            previous = state.get(client_id) or {}
            state[client_id] = {
                "last_failed_at": _utcnow().isoformat(),
                "failed_paths": list(result.get("failed_paths") or []),
                "docs_failed": int(result.get("docs_failed") or 0),
                "consecutive_failures": int(previous.get("consecutive_failures") or 0) + 1,
            }
            changed = True
            continue

        if client_id in state:
            state.pop(client_id, None)
            changed = True

    if changed:
        _save_failure_state(state)


def _list_clients_with_active_documents() -> list[str]:
    rows = (
        supabase.table("document_metadata")
        .select("client_id")
        .eq("is_active", True)
        .execute()
    ).data or []
    return sorted(
        {
            str(row.get("client_id") or "").strip()
            for row in rows
            if str(row.get("client_id") or "").strip()
        }
    )


def _select_target_client_ids_with_context(payload: ReindexBatchPayload) -> dict:
    if payload.client_ids:
        return {
            "selected_client_ids": [
                client_id.strip()
                for client_id in payload.client_ids
                if str(client_id or "").strip()
            ][: payload.max_clients],
            "skipped_due_to_recent_failures": [],
        }

    if payload.only_at_risk:
        candidate_ids = [
            row["client_id"]
            for row in audit_document_index_health().get("at_risk_clients", [])
        ]
    else:
        candidate_ids = _list_clients_with_active_documents()

    retryable_ids, skipped_client_ids = _filter_retryable_client_ids(candidate_ids)
    return {
        "selected_client_ids": retryable_ids[: payload.max_clients],
        "skipped_due_to_recent_failures": skipped_client_ids,
    }


def _select_target_client_ids(payload: ReindexBatchPayload) -> list[str]:
    return _select_target_client_ids_with_context(payload)["selected_client_ids"]


def _lock_path() -> Path:
    return Path(get_base_data_path()) / ".reindex-batch.lock"


def _load_lock_state() -> dict | None:
    lock_path = _lock_path()
    if not lock_path.exists():
        return None

    try:
        stat = lock_path.stat()
        file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    except Exception:
        file_mtime = None

    try:
        raw_content = lock_path.read_text(encoding="utf-8").strip()
    except Exception:
        return {
            "lock_path": str(lock_path),
            "read_error": True,
            "file_mtime": file_mtime,
        }

    if not raw_content:
        return {
            "lock_path": str(lock_path),
            "acquired_at": None,
            "selected_client_ids": [],
            "format": "empty",
            "file_mtime": file_mtime,
        }

    try:
        parsed = json.loads(raw_content)
        if isinstance(parsed, dict):
            state = dict(parsed)
            state.setdefault("selected_client_ids", [])
            state["lock_path"] = str(lock_path)
            state["format"] = "json"
            state["file_mtime"] = file_mtime
            return state
    except Exception:
        pass

    parsed_timestamp = _parse_iso_timestamp(raw_content)
    return {
        "lock_path": str(lock_path),
        "acquired_at": parsed_timestamp.isoformat() if parsed_timestamp else raw_content,
        "selected_client_ids": [],
        "format": "legacy_text",
        "file_mtime": file_mtime,
    }


def _lock_age_seconds(lock_state: dict | None) -> float | None:
    if not lock_state:
        return None
    acquired_at = _parse_iso_timestamp(lock_state.get("acquired_at")) or _parse_iso_timestamp(
        lock_state.get("file_mtime")
    )
    if not acquired_at:
        return None
    age = (_utcnow() - acquired_at).total_seconds()
    return max(age, 0.0)


def _is_lock_stale(lock_state: dict | None) -> bool:
    age_seconds = _lock_age_seconds(lock_state)
    if age_seconds is None:
        return False
    return age_seconds >= LOCK_STALE_AFTER_MINUTES * 60


def _write_lock_state(handle, *, selected_client_ids: list[str]) -> None:
    state = {
        "acquired_at": _utcnow().isoformat(),
        "selected_client_ids": list(selected_client_ids),
        "pid": os.getpid(),
    }
    handle.write(json.dumps(state, ensure_ascii=True, sort_keys=True))
    handle.flush()


@contextmanager
def _reindex_lock(*, selected_client_ids: list[str] | None = None):
    lock_path = _lock_path()
    acquired = False

    for _attempt in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                _write_lock_state(handle, selected_client_ids=selected_client_ids or [])
            acquired = True
            break
        except FileExistsError:
            lock_state = _load_lock_state()
            if _is_lock_stale(lock_state):
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    raise HTTPException(status_code=409, detail="reindex_batch_already_running")
                continue
            raise HTTPException(status_code=409, detail="reindex_batch_already_running")

    if not acquired:
        raise HTTPException(status_code=409, detail="reindex_batch_already_running")

    try:
        yield lock_path
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.get("/health")
def get_indexing_health(request: Request):
    require_internal_request(request)
    return {
        "runtime": _runtime_context(),
        "audit": audit_document_index_health(),
        "recent_failures": _load_failure_state(),
        "active_lock": _load_lock_state(),
    }


@router.post("/reindex-stale")
def reindex_stale_clients(payload: ReindexBatchPayload, request: Request):
    require_internal_request(request)

    selection = _select_target_client_ids_with_context(payload)
    target_client_ids = selection["selected_client_ids"]
    skipped_client_ids = selection["skipped_due_to_recent_failures"]
    if not target_client_ids:
        return {
            "status": "cooldown" if skipped_client_ids else "no_targets",
            "runtime": _runtime_context(),
            "selected_client_ids": [],
            "skipped_due_to_recent_failures": skipped_client_ids,
            "results": [],
        }

    try:
        with _reindex_lock(selected_client_ids=target_client_ids):
            results = [reindex_client(client_id) for client_id in target_client_ids]
            _remember_reindex_results(results)
    except HTTPException as error:
        if error.detail == "reindex_batch_already_running":
            return {
                "status": "locked",
                "runtime": _runtime_context(),
                "selected_client_ids": target_client_ids,
                "skipped_due_to_recent_failures": skipped_client_ids,
                "active_lock": _load_lock_state(),
                "results": [],
            }
        raise

    failed = [result for result in results if result.get("status") == "partial_failure"]
    status = "partial_failure" if failed else "success"

    return {
        "status": status,
        "runtime": _runtime_context(),
        "selected_client_ids": target_client_ids,
        "skipped_due_to_recent_failures": skipped_client_ids,
        "processed_clients": len(results),
        "failed_clients": len(failed),
        "results": results,
    }
