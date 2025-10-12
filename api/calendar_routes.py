from fastapi import APIRouter, Query
from api.modules.calendar_logic import get_availability_from_google_calendar as get_availability
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

@router.get("/calendar_availability")
def get_calendar_availability(client_id: str = Query(...)) -> dict:
    return get_availability(client_id)

@router.get("/auth/google_calendar")
async def check_google_calendar_connection(client_id: str = Query(...)):
    """
    Verifica si el cliente tiene integración activa con Google Calendar.
    """
    try:
        res = supabase.table("calendar_integrations")\
            .select("connected_email, is_active")\
            .eq("client_id", client_id)\
            .eq("is_active", True)\
            .limit(1)\
            .execute()

        if not res or not res.data:
            return {"connected": False}

        record = res.data[0]
        return {
            "connected": record.get("is_active", False),
            "connected_email": record.get("connected_email")
        }

    except Exception as e:
        print(f"❌ Error al verificar conexión de Google Calendar: {e}")
        return {"connected": False}
