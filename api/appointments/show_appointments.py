# api/appointments/show_appointments.py

from fastapi import APIRouter, HTTPException, Query
from uuid import UUID
import logging

from api.config.config import supabase

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"]
)

logger = logging.getLogger(__name__)


@router.get("/show")  # ⬅️ ESTO es lo que te está faltando
def show_appointments(
    client_id: UUID = Query(..., description="Client ID")
):
    """
    Returns all appointments for a client (read-only).
    """

    try:
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

        return response.data or []

    except Exception as e:
        logger.exception("Failed to fetch appointments")
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch appointments"
        )
