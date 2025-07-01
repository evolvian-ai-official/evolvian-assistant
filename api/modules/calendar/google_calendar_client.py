import logging
from datetime import datetime, timedelta
import pytz
import requests

from api.modules.assistant_rag.supabase_client import supabase

logger = logging.getLogger(__name__)

def get_availability_from_google_calendar(client_id: str) -> dict:
    try:
        logger.info(f"📅 Verificando disponibilidad para client_id: {client_id}")
        
        # Obtener integración
        res = supabase.table("calendar_integrations").select("access_token, calendar_id").eq("client_id", client_id).maybe_single().execute()
        data = res.data
        if not data:
            return {"available_slots": [], "message": "No se encontró integración de Google Calendar."}

        access_token = data["access_token"]
        calendar_id = data["calendar_id"]

        tz = pytz.timezone("America/Mexico_City")
        now = datetime.now(tz)
        time_min = now
        time_max = now + timedelta(days=7)

        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": "America/Mexico_City",
            "items": [{"id": calendar_id}]
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post("https://www.googleapis.com/calendar/v3/freeBusy", headers=headers, json=body)
        response.raise_for_status()
        busy = response.json()["calendars"][calendar_id]["busy"]
        busy = sorted([
            (
                datetime.fromisoformat(b["start"]).astimezone(tz),
                datetime.fromisoformat(b["end"]).astimezone(tz)
            )
            for b in busy
        ])

        available_slots = []
        min_duration = timedelta(minutes=30)
        pointer = now

        if not busy:
            logger.info("📭 Calendario vacío, generando disponibilidad completa")
            current = now.replace(hour=9, minute=0, second=0, microsecond=0)
            while current < time_max:
                if current.time() >= datetime.strptime("09:00", "%H:%M").time() and current.time() < datetime.strptime("17:00", "%H:%M").time():
                    available_slots.append(current.isoformat())
                current += timedelta(minutes=30)
                if current.time() >= datetime.strptime("17:00", "%H:%M").time():
                    current = current + timedelta(days=1)
                    current = current.replace(hour=9, minute=0)
        else:
            for start, end in busy:
                if (start - pointer) >= min_duration:
                    available_slots.append(pointer.isoformat())
                pointer = max(pointer, end)

            if (time_max - pointer) >= min_duration:
                available_slots.append(pointer.isoformat())

        if not available_slots:
            logger.info("⚠️ No se encontraron horarios disponibles")
            return {"available_slots": [], "message": "No hay horarios libres en los próximos 7 días."}

        logger.info(f"✅ {len(available_slots)} slots disponibles")
        return {"available_slots": available_slots[:10], "message": "Horarios disponibles encontrados"}

    except Exception as e:
        logger.exception("❌ Error al obtener disponibilidad desde Google Calendar")
        return {"available_slots": [], "message": f"Error al consultar disponibilidad: {str(e)}"}
