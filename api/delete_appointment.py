from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
import requests
import logging
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(tags=["Calendar"])
logger = logging.getLogger("delete_appointment")


@router.delete("/calendar/appointment/{appointment_id}")
def delete_appointment(
    appointment_id: str = Path(..., description="UUID of the appointment to delete"),
    client_id: str = Query(..., description="Client ID for authentication"),
):
    """
    Deletes an appointment both from Supabase and Google Calendar.

    ✅ Removes the event from Google Calendar
    ✅ Deletes the record in Supabase
    ✅ Returns clean JSON for UI confirmation
    """

    logger.info(f"🗑️ Deleting appointment {appointment_id} for client_id={client_id}")

    try:
        # 1️⃣ Fetch the appointment
        appt_res = (
            supabase.table("appointments")
            .select("calendar_event_id, scheduled_time")
            .eq("id", appointment_id)
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )

        appointment = appt_res.data
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        calendar_event_id = appointment["calendar_event_id"]

        # 2️⃣ Fetch calendar integration
        integ_res = (
            supabase.table("calendar_integrations")
            .select("access_token, calendar_id")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        integration = integ_res.data
        if not integration:
            raise HTTPException(status_code=404, detail="Active calendar integration not found")

        access_token = integration["access_token"]
        calendar_id = integration["calendar_id"]

        # 3️⃣ Try to delete from Google Calendar
        if calendar_event_id:
            delete_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{calendar_event_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            google_res = requests.delete(delete_url, headers=headers)

            if google_res.status_code not in (204, 404):
                logger.error(f"❌ Google Calendar delete failed: {google_res.status_code} - {google_res.text}")
                raise HTTPException(status_code=google_res.status_code, detail="Failed to delete from Google Calendar")

            logger.info(f"✅ Google Calendar event deleted: {calendar_event_id}")

        # 4️⃣ Delete from Supabase
        supabase.table("appointments").delete().eq("id", appointment_id).execute()
        logger.info("🧹 Appointment deleted from Supabase")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Appointment deleted successfully.",
                "deleted_id": appointment_id,
            },
        )

    except HTTPException as e:
        logger.warning(f"⚠️ {e.detail}")
        raise e
    except Exception as e:
        logger.exception("❌ Unexpected error while deleting appointment")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
