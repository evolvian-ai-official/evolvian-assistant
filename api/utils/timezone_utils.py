from zoneinfo import ZoneInfo, available_timezones
import logging
from api.config.config import supabase

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "UTC"


def get_client_timezone(client_id: str) -> ZoneInfo:
    """
    Returns a safe ZoneInfo object for the client.
    - Validates against IANA timezone database.
    - Falls back to UTC if missing or invalid.
    - Never raises exception.
    """

    try:
        response = (
            supabase
            .table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            logger.warning(
                "⚠️ No timezone configured | client_id=%s | using UTC",
                client_id,
            )
            return ZoneInfo(DEFAULT_TIMEZONE)

        tz_str = response.data[0].get("timezone") or DEFAULT_TIMEZONE

        # 🔒 Validate against official IANA list
        if tz_str not in available_timezones():
            logger.error(
                "❌ Invalid timezone in DB | client_id=%s | tz=%s | fallback=UTC",
                client_id,
                tz_str,
            )
            return ZoneInfo(DEFAULT_TIMEZONE)

        return ZoneInfo(tz_str)

    except Exception as e:
        logger.exception(
            "❌ Failed to resolve client timezone | client_id=%s | error=%s",
            client_id,
            e,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)
