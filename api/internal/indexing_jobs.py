from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.config.config import supabase
from api.internal.audit_document_index_health import audit_document_index_health
from api.internal.reindex_single_client import reindex_client
from api.internal_auth import require_internal_request
from api.utils.paths import get_base_data_path


router = APIRouter(
    prefix="/api/internal/indexing",
    tags=["Indexing Internal"],
)


class ReindexBatchPayload(BaseModel):
    client_ids: list[str] | None = None
    max_clients: int = Field(default=1, ge=1, le=25)
    only_at_risk: bool = True


def _runtime_context() -> dict:
    base_data_path = get_base_data_path()
    render_disk_mount = (os.getenv("RENDER_DISK_MOUNT_PATH") or "").strip()
    return {
        "base_data_path": base_data_path,
        "render_disk_configured": bool(render_disk_mount),
        "render_disk_mount_path": render_disk_mount or None,
        "running_on_render": os.path.exists("/opt/render/project/src"),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


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


def _select_target_client_ids(payload: ReindexBatchPayload) -> list[str]:
    if payload.client_ids:
        return [
            client_id.strip()
            for client_id in payload.client_ids
            if str(client_id or "").strip()
        ][: payload.max_clients]

    if payload.only_at_risk:
        audit = audit_document_index_health()
        return [
            row["client_id"]
            for row in audit.get("at_risk_clients", [])
        ][: payload.max_clients]

    return _list_clients_with_active_documents()[: payload.max_clients]


def _lock_path() -> Path:
    return Path(get_base_data_path()) / ".reindex-batch.lock"


@contextmanager
def _reindex_lock():
    lock_path = _lock_path()
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(datetime.now(timezone.utc).isoformat())
    except FileExistsError:
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
    }


@router.post("/reindex-stale")
def reindex_stale_clients(payload: ReindexBatchPayload, request: Request):
    require_internal_request(request)

    target_client_ids = _select_target_client_ids(payload)
    if not target_client_ids:
        return {
            "status": "no_targets",
            "runtime": _runtime_context(),
            "selected_client_ids": [],
            "results": [],
        }

    try:
        with _reindex_lock():
            results = [reindex_client(client_id) for client_id in target_client_ids]
    except HTTPException as error:
        if error.detail == "reindex_batch_already_running":
            return {
                "status": "locked",
                "runtime": _runtime_context(),
                "selected_client_ids": target_client_ids,
                "results": [],
            }
        raise

    failed = [result for result in results if result.get("status") == "partial_failure"]
    status = "partial_failure" if failed else "success"

    return {
        "status": status,
        "runtime": _runtime_context(),
        "selected_client_ids": target_client_ids,
        "processed_clients": len(results),
        "failed_clients": len(failed),
        "results": results,
    }
