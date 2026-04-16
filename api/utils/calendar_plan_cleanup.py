import logging
from datetime import datetime
from typing import Any

from api.config.config import supabase
from api.utils.effective_plan import normalize_plan_id, resolve_effective_plan_id


logger = logging.getLogger(__name__)

CALENDAR_SYNC_FEATURE = "calendar_sync"
WIDGET_CALENDAR_BOOKING_FEATURE = "widget_calendar_booking"
CALENDAR_AI_CHAT_FEATURE = "calendar_ai_chat"
CALENDAR_AI_WHATSAPP_FEATURE = "calendar_ai_whatsapp"
GOOGLE_CALENDAR_SYNC_FEATURE = "google_calendar_sync"


def _normalize_feature_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _load_active_plan_features(plan_id: str, *, supabase_client: Any) -> set[str]:
    if not plan_id:
        return set()

    res = (
        supabase_client.table("plan_features")
        .select("feature")
        .eq("plan_id", plan_id)
        .eq("is_active", True)
        .execute()
    )
    return {
        _normalize_feature_key(row.get("feature"))
        for row in (getattr(res, "data", None) or [])
        if _normalize_feature_key(row.get("feature"))
    }


def disconnect_calendar_features_for_plan(
    client_id: str,
    *,
    base_plan_id: str | None = None,
    supabase_client: Any = None,
) -> dict[str, Any]:
    try:
        client = supabase_client or supabase
        effective_plan_id = resolve_effective_plan_id(
            client_id,
            base_plan_id=normalize_plan_id(base_plan_id),
            supabase_client=client,
        )
        features = _load_active_plan_features(effective_plan_id, supabase_client=client)

        has_calendar_sync = CALENDAR_SYNC_FEATURE in features
        widget_enabled = has_calendar_sync and WIDGET_CALENDAR_BOOKING_FEATURE in features
        chat_ai_enabled = has_calendar_sync and CALENDAR_AI_CHAT_FEATURE in features
        whatsapp_ai_enabled = has_calendar_sync and CALENDAR_AI_WHATSAPP_FEATURE in features
        google_sync_enabled = has_calendar_sync and GOOGLE_CALENDAR_SYNC_FEATURE in features

        settings_updates: dict[str, Any] = {}
        if not widget_enabled:
            settings_updates["show_agenda_in_chat_widget"] = False
        if not chat_ai_enabled:
            settings_updates["ai_scheduling_chat_enabled"] = False
        if not whatsapp_ai_enabled:
            settings_updates["ai_scheduling_whatsapp_enabled"] = False

        result = {
            "client_id": client_id,
            "effective_plan_id": effective_plan_id,
            "settings_updated": False,
            "google_disconnected": False,
            "settings_fields_reset": sorted(settings_updates.keys()),
        }

        if settings_updates:
            settings_updates["updated_at"] = datetime.utcnow().isoformat()
            try:
                existing = (
                    client.table("calendar_settings")
                    .select("client_id")
                    .eq("client_id", client_id)
                    .limit(1)
                    .execute()
                )
                if getattr(existing, "data", None):
                    (
                        client.table("calendar_settings")
                        .update(settings_updates)
                        .eq("client_id", client_id)
                        .execute()
                    )
                else:
                    client.table("calendar_settings").insert(
                        {"client_id": client_id, **settings_updates}
                    ).execute()
                result["settings_updated"] = True
            except Exception as exc:
                logger.warning(
                    "Could not reset calendar settings for downgraded plan | client_id=%s | plan_id=%s | err=%s",
                    client_id,
                    effective_plan_id,
                    exc,
                )

        if not google_sync_enabled:
            try:
                (
                    client.table("calendar_integrations")
                    .update({"is_active": False, "connected_email": None})
                    .eq("client_id", client_id)
                    .eq("is_active", True)
                    .execute()
                )
                result["google_disconnected"] = True
            except Exception as exc:
                logger.warning(
                    "Could not disconnect Google Calendar for downgraded plan | client_id=%s | plan_id=%s | err=%s",
                    client_id,
                    effective_plan_id,
                    exc,
                )

        return result
    except Exception as exc:
        logger.warning(
            "Could not enforce calendar feature cleanup for plan change | client_id=%s | base_plan_id=%s | err=%s",
            client_id,
            base_plan_id,
            exc,
        )
        return {
            "client_id": client_id,
            "effective_plan_id": normalize_plan_id(base_plan_id) or "free",
            "settings_updated": False,
            "google_disconnected": False,
            "settings_fields_reset": [],
        }
