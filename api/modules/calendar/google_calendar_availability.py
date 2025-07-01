from .google_calendar_client import get_access_token_from_supabase, fetch_calendar_events
from datetime import datetime, timedelta
import pytz

def get_availability_from_google_calendar(client_id: str) -> dict:
    """
    Consulta eventos ocupados en Google Calendar y devuelve los horarios libres.
    """
    tz = pytz.timezone("America/Mexico_City")
    now = datetime.now(tz)
    end = now + timedelta(days=5)

    # Paso 1: obtener access_token desde Supabase
    access_token = get_access_token_from_supabase(client_id)
    
    # Paso 2: obtener eventos ocupados desde Google Calendar
    busy_slots = fetch_calendar_events(access_token, now, end)

    # Paso 3: definir posibles slots y excluir los ocupados
    available_slots = []
    for day_offset in range(5):
        date = now + timedelta(days=day_offset)
        for hour in range(10, 17):
            candidate = tz.localize(datetime(date.year, date.month, date.day, hour, 0))
            if not any(busy_start <= candidate < busy_end for (busy_start, busy_end) in busy_slots):
                available_slots.append(candidate.isoformat())

    return {"available_slots": available_slots}
