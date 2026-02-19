from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from api.compliance.incident_readiness import (
    REQUIRED_INCIDENT_SECRETS,
    build_incident_readiness_snapshot,
)
from api.internal_auth import require_internal_request


router = APIRouter(
    prefix="/api/internal/compliance/incident",
    tags=["Compliance Incident Internal"],
)


@router.get("/runbook")
def get_incident_runbook_reference(request: Request):
    require_internal_request(request)
    return {
        "runbook_path": "docs/compliance/phase2_incident_runbook.md",
        "templates": [
            "docs/compliance/templates/incident_notification_internal.md",
            "docs/compliance/templates/incident_notification_california.md",
            "docs/compliance/templates/incident_notification_gdpr.md",
        ],
        "required_secrets": REQUIRED_INCIDENT_SECRETS,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/readiness")
def get_incident_readiness_snapshot(
    request: Request,
    window_hours: int = Query(default=24, ge=1, le=24 * 30),
    max_rows: int = Query(default=2000, ge=100, le=10000),
):
    require_internal_request(request)
    return build_incident_readiness_snapshot(
        window_hours=window_hours,
        max_rows=max_rows,
    )

