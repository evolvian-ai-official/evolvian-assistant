from api.utils.feature_access import client_has_all_active_features


CALENDAR_SYNC_FEATURE = "calendar_sync"
MANUAL_APPOINTMENT_CREATION_FEATURE = "manual_appointment_creation"
WIDGET_CALENDAR_BOOKING_FEATURE = "widget_calendar_booking"
CALENDAR_AI_CHAT_FEATURE = "calendar_ai_chat"
CALENDAR_AI_WHATSAPP_FEATURE = "calendar_ai_whatsapp"
GOOGLE_CALENDAR_SYNC_FEATURE = "google_calendar_sync"


def client_can_use_manual_appointment_creation(client_id: str) -> bool:
    return client_has_all_active_features(
        client_id,
        CALENDAR_SYNC_FEATURE,
        MANUAL_APPOINTMENT_CREATION_FEATURE,
    )


def client_can_use_widget_calendar_booking(client_id: str) -> bool:
    return client_has_all_active_features(
        client_id,
        CALENDAR_SYNC_FEATURE,
        WIDGET_CALENDAR_BOOKING_FEATURE,
    )


def client_can_use_calendar_ai_for_channel(client_id: str, channel: str | None) -> bool:
    normalized = str(channel or "").strip().lower()
    required_features = [CALENDAR_SYNC_FEATURE]
    if normalized == "whatsapp":
        required_features.append(CALENDAR_AI_WHATSAPP_FEATURE)
    elif normalized in {"chat", "widget", "web", "chat_widget"}:
        required_features.append(CALENDAR_AI_CHAT_FEATURE)
    return client_has_all_active_features(client_id, *required_features)


def client_can_use_google_calendar_sync(client_id: str) -> bool:
    return client_has_all_active_features(
        client_id,
        CALENDAR_SYNC_FEATURE,
        GOOGLE_CALENDAR_SYNC_FEATURE,
    )
