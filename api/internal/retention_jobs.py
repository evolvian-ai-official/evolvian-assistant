from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.compliance.retention_policy import (
    RETENTION_APPLY_ENV,
    get_rule_map,
    is_retention_apply_allowed,
    rule_to_dict,
    run_retention_job,
)
from api.internal_auth import require_internal_request


router = APIRouter(
    prefix="/api/internal/compliance/retention",
    tags=["Compliance Retention Internal"],
)


class RetentionRunPayload(BaseModel):
    apply: bool = False
    tables: list[str] | None = None
    batch_size: int = Field(default=500, ge=1, le=1000)
    max_batches: int = Field(default=20, ge=1, le=200)
    confirmation: str = Field(default="")


@router.get("/rules")
def get_retention_rules(request: Request):
    require_internal_request(request)
    now = datetime.now(timezone.utc)
    rules = [rule_to_dict(rule, now=now) for rule in get_rule_map().values()]
    return {
        "rules": rules,
        "apply_allowed": is_retention_apply_allowed(),
        "apply_env_var": RETENTION_APPLY_ENV,
        "snapshot_at": now.isoformat(),
    }


@router.post("/run")
def execute_retention_job(payload: RetentionRunPayload, request: Request):
    require_internal_request(request)

    if payload.apply and payload.confirmation.strip() != "APPLY_RETENTION_JOB":
        raise HTTPException(
            status_code=400,
            detail="confirmation_required: set confirmation=APPLY_RETENTION_JOB to run apply mode",
        )

    try:
        result = run_retention_job(
            apply=payload.apply,
            tables=payload.tables,
            batch_size=payload.batch_size,
            max_batches=payload.max_batches,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"retention_job_failed: {error}") from error

    return result

