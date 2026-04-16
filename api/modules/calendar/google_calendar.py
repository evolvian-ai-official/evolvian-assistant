import requests
import datetime
import pytz
from datetime import timedelta
from api.modules.assistant_rag.supabase_client import supabase
import os
import logging
from api.utils.calendar_feature_flags import client_can_use_google_calendar_sync

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

def refresh_access_token(refresh_token: str) -> str:
    logger.info("🔄 Refrescando access_token con refresh_token...")
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    response = requests.post(token_url, data=payload)
    response.raise_for_status()
    new_access_token = response.json().get("access_token")

    if not new_access_token:
        raise ValueError("No se pudo obtener un nuevo access_token")

    return new_access_token

def get_availability_from_google_calendar(client_id: str, days_ahead: int = 7) -> dict:
    try:
        logger.info(f"📅 Verificando disponibilidad real para client_id: {client_id}")
        if not client_can_use_google_calendar_sync(client_id):
            return {"available_slots": [], "message": "Google Calendar sync no está habilitado para este plan"}
        tz = pytz.timezone("America/Mexico_City")
        now = datetime.datetime.now(tz)
        end_range = now + timedelta(days=days_ahead)

        # 📥 Obtener integración activa
        resp = supabase.table("calendar_integrations").select("access_token, refresh_token, calendar_id").eq("client_id", client_id).eq("is_active", True).maybe_single().execute()
        data = resp.data
        if not data:
            return {"available_slots": [], "message": "No se encontró integración con Google Calendar"}

        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        calendar_id = data["calendar_id"]

        def consultar_disponibilidad(token_actual):
            headers = {
                "Authorization": f"Bearer {token_actual}",
                "Content-Type": "application/json"
            }
            body = {
                "timeMin": now.isoformat(),
                "timeMax": end_range.isoformat(),
                "timeZone": "America/Mexico_City",
                "items": [{"id": calendar_id}]
            }
            return requests.post("https://www.googleapis.com/calendar/v3/freeBusy", headers=headers, json=body)

        # 🔍 Primer intento
        res = consultar_disponibilidad(access_token)

        # 🔄 Si falló por token expirado, intentamos refrescarlo
        if res.status_code == 401:
            logger.warning("⚠️ access_token expirado, intentando refrescar...")
            access_token = refresh_access_token(refresh_token)

            # Guardar el nuevo access_token en Supabase
            supabase.table("calendar_integrations").update({"access_token": access_token}).eq("client_id", client_id).execute()

            # Intentar de nuevo con el token nuevo
            res = consultar_disponibilidad(access_token)

        res.raise_for_status()
        busy_blocks = res.json()["calendars"][calendar_id]["busy"]

        busy_ranges = [
            (
                datetime.datetime.fromisoformat(b["start"]).astimezone(tz),
                datetime.datetime.fromisoformat(b["end"]).astimezone(tz)
            )
            for b in busy_blocks
        ]

        # ⏱️ Generar slots posibles (9am a 6pm cada 30 minutos)
        available_slots = []
        slot_duration = timedelta(minutes=30)
        current = now.replace(minute=0, second=0, microsecond=0)

        while current < end_range:
            if 9 <= current.hour < 18:
                overlaps = any(start <= current < end for start, end in busy_ranges)
                if not overlaps:
                    available_slots.append(current.isoformat())
            current += slot_duration

        logger.info(f"✅ {len(available_slots)} horarios libres detectados")
        return {"available_slots": available_slots[:10], "message": "Horarios disponibles generados"}

    except Exception as e:
        logger.exception("❌ Error al consultar disponibilidad en Google Calendar")
        return {"available_slots": [], "message": f"Error al consultar disponibilidad: {str(e)}"}
