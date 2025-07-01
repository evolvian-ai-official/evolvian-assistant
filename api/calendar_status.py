# api/calendar_status.py

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.calendar_logic import get_availability_from_google_calendar as get_availability


router = APIRouter()

@router.get("/calendar/status")
def get_calendar_status(client_id: str = Query(...)):
    try:
        result = supabase.table("calendar_integrations")\
            .select("id")\
            .eq("client_id", client_id)\
            .eq("is_active", True)\
            .maybe_single()\
            .execute()

        connected = bool(result.data)

        slots = []
        if connected:
            calendar_data = get_availability(client_id)
            slots = calendar_data.get("available_slots", [])

        return JSONResponse({
            "connected": connected,
            "available_slots": slots
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
