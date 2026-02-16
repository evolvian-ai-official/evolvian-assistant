# api/calendar_status.py

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
from api.modules.calendar_logic import get_availability_from_google_calendar as get_availability


router = APIRouter()

@router.get("/calendar/status")
def get_calendar_status(request: Request, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)
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
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
