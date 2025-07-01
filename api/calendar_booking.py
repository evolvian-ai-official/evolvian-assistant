# api/calendar_booking.py

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import requests
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

@router.post("/calendar/book")
def book_event(
    client_id: str = Form(...),
    user_email: str = Form(...),
    user_name: str = Form(...),
    scheduled_time: str = Form(...),  # Formato ISO 8601 esperado
):
    try:
        # Buscar integración de Google Calendar
        integration = supabase.table("calendar_integrations")\
            .select("access_token, calendar_id, timezone")\
            .eq("client_id", client_id)\
            .eq("is_active", True)\
            .maybe_single()\
            .execute()

        if not integration.data:
            return JSONResponse(status_code=400, content={"error": "No calendar integration found."})

        access_token = integration.data["access_token"]
        calendar_id = integration.data["calendar_id"]
        timezone = integration.data.get("timezone", "America/Mexico_City")

        # Crear evento
        start = datetime.fromisoformat(scheduled_time)
        end = start + timedelta(hours=1)

        event = {
            "summary": f"Cita con {user_name}",
            "description": f"Agendada por Evolvian AI Assistant para {user_email}",
            "start": {
                "dateTime": start.isoformat(),
                "timeZone": timezone
            },
            "end": {
                "dateTime": end.isoformat(),
                "timeZone": timezone
            },
            "attendees": [{"email": user_email}],
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

        res = requests.post(url, headers=headers, json=event)

        if res.status_code >= 400:
            return JSONResponse(status_code=500, content={
                "error": f"Google Calendar error: {res.status_code}",
                "details": res.json()
            })

        data = res.json()
        return JSONResponse(content={
            "message": "Evento agendado con éxito.",
            "event_link": data.get("htmlLink")
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
