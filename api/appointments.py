from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
import logging

router = APIRouter(tags=["Calendar"])
logger = logging.getLogger("appointments")


@router.get("/calendar/appointments")
def list_appointments(client_id: str = Query(...)):
    """
    Returns all booked appointments for a specific client.

    ✅ Reads from Supabase table `appointments`
    ✅ Sorted by scheduled_time ascending
    ✅ Includes user name, email, and calendar_event_id
    """

    logger.info(f"📋 Fetching appointments for client_id={client_id}")

    try:
        res = (
            supabase.table("appointments")
            .select("id, user_name, user_email, scheduled_time, created_at, calendar_event_id")
            .eq("client_id", client_id)
            .order("scheduled_time", desc=False)
            .execute()
        )

        appointments = res.data or []

        if not appointments:
            logger.info("⚠️ No appointments found for this client.")
            return JSONResponse(
                status_code=200,
                content={"appointments": [], "message": "No appointments found for this client."},
            )

        formatted = [
            {
                "id": appt["id"],
                "user_name": appt.get("user_name", "N/A"),
                "user_email": appt.get("user_email", "N/A"),
                "scheduled_time": appt.get("scheduled_time"),
                "created_at": appt.get("created_at"),
                "calendar_event_id": appt.get("calendar_event_id"),
            }
            for appt in appointments
        ]

        logger.info(f"✅ {len(formatted)} appointments retrieved successfully.")
        return JSONResponse(status_code=200, content={"appointments": formatted})

    except Exception as e:
        logger.exception("❌ Error while fetching appointments")
        return JSONResponse(status_code=500, content={"error": str(e), "appointments": []})
