# api/appointments/show_appointments.py

from fastapi import APIRouter, HTTPException, Query, Request
from uuid import UUID
import logging
from datetime import datetime

from api.config.config import supabase
from api.authz import authorize_client_request

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"]
)

logger = logging.getLogger(__name__)


def _is_valid_datetime(value) -> bool:
    if not value or not isinstance(value, str):
        return False
    raw = value.strip()
    if not raw:
        return False
    try:
        normalized = raw.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return True
    except Exception:
        return False


@router.get("/show")
def show_appointments(
    request: Request,
    client_id: UUID = Query(..., description="Client ID")
):
    """
    Returns all appointments for a client (read-only).
    """

    try:
        authorize_client_request(request, str(client_id))

        response = (
            supabase
            .table("appointments")
            .select(
                "id, user_name, user_email, user_phone, "
                "scheduled_time, appointment_type, channel, status, created_at"
            )
            .eq("client_id", str(client_id))
            .order("scheduled_time", desc=True)
            .execute()
        )

        rows = response.data or []
        clean_rows = []
        for row in rows:
            scheduled_time = row.get("scheduled_time") if isinstance(row, dict) else None
            if not _is_valid_datetime(scheduled_time):
                logger.warning("Skipping appointment with invalid scheduled_time. id=%s", row.get("id") if isinstance(row, dict) else None)
                continue
            clean_rows.append(row)

        return clean_rows

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch appointments")
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch appointments"
        )
