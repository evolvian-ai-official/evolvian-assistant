import os
import logging
from datetime import datetime, timedelta
from typing import List
import pytz

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.calendar.google_calendar_availability import get_availability_from_google_calendar

logger = logging.getLogger("calendar_availability")

ENV = os.getenv("ENV", "local").lower()  # 'local', 'qa', 'prod'


def get_availability(client_id: str) -> dict:
    """
    Returns available time slots for a given client.

    - If the client has an active Google Calendar integration → uses real data.
    - If not → falls back to the client's manual schedule settings.
    - If running locally → generates mock time slots for testing.
    """

    logger.info(f"📅 Fetching availability for client_id={client_id} (ENV={ENV})")

    try:
        # 1️⃣ Check if the client has an active Google Calendar integration
        integration = (
            supabase.table("calendar_integrations")
            .select("is_active")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        has_calendar = bool(integration.data)

        # 2️⃣ If in prod/qa and integration is active → use real Google Calendar data
        if ENV in ["prod", "qa"] and has_calendar:
            logger.info("🔗 Active Google Calendar integration: fetching real availability.")
            availability = get_availability_from_google_calendar(client_id)
            return {
                "source": "google_calendar",
                "available": True,
                "available_slots": availability.get("available_slots", []),
            }

        # 3️⃣ If no Google Calendar → use client’s manual schedule settings
        schedule = (
            supabase.table("client_schedule_settings")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if schedule.data:
            config = schedule.data[0]
            logger.info(f"🕒 Using manual schedule configuration for {client_id}")
            return {
                "source": "manual_schedule",
                "available": True,
                "working_days": config.get("working_days"),
                "availability_start": config.get("availability_start"),
                "availability_end": config.get("availability_end"),
                "timezone": config.get("timezone"),
            }

        # 4️⃣ In local environment → generate mock time slots
        if ENV == "local":
            tz = pytz.timezone("America/Mexico_City")
            now = datetime.now(tz)
            available_slots: List[str] = []

            for day_offset in range(5):
                date = now + timedelta(days=day_offset)
                for hour in range(10, 17):
                    slot = tz.localize(
                        datetime(
                            year=date.year,
                            month=date.month,
                            day=date.day,
                            hour=hour,
                            minute=0,
                            second=0,
                        )
                    )
                    available_slots.append(slot.isoformat())

            logger.info(f"🧪 {len(available_slots)} mock slots generated for {client_id}")
            return {
                "source": "simulated",
                "available": True,
                "available_slots": available_slots,
            }

        # 5️⃣ If no data found
        logger.warning(f"⚠️ No availability found for client_id={client_id}")
        return {
            "source": "none",
            "available": False,
            "message": "No availability found for this client",
        }

    except Exception as e:
        logger.error(f"❌ Error in get_availability: {str(e)}")
        return {"available": False, "error": str(e)}
