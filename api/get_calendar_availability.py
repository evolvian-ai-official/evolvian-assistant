import os
import logging
from datetime import datetime, timedelta
from typing import List
import pytz

from api.modules.calendar.google_calendar_availability import get_availability_from_google_calendar

logger = logging.getLogger("calendar_logic")

ENV = os.getenv("ENV", "local").lower()  # 'local', 'qa', 'prod'

def get_availability(client_id: str) -> dict:
    """
    Devuelve horarios disponibles desde Google Calendar si está en QA/PROD,
    y simulados si está en LOCAL (modo desarrollo).
    """
    logger.info(f"📅 Obteniendo disponibilidad para client_id: {client_id} (ENV: {ENV})")

    try:
        if ENV in ["prod", "qa"]:
            return get_availability_from_google_calendar(client_id)
        else:
            # Simulado para desarrollo local
            tz = pytz.timezone("America/Mexico_City")
            now = datetime.now(tz)
            available_slots: List[str] = []

            for day_offset in range(5):
                date = now + timedelta(days=day_offset)
                for hour in range(10, 17):
                    slot = tz.localize(datetime(
                        year=date.year,
                        month=date.month,
                        day=date.day,
                        hour=hour,
                        minute=0,
                        second=0
                    ))
                    available_slots.append(slot.isoformat())

            logger.info(f"🧪 {len(available_slots)} horarios simulados generados para {client_id}")
            return {"available_slots": available_slots}

    except Exception as e:
        logger.error(f"❌ Error en get_availability: {str(e)}")
        return {"error": "Error interno al obtener disponibilidad"}
