# api/modules/calendar/get_booked_slots.py

from api.modules.assistant_rag.supabase_client import supabase

def get_booked_slots(client_id: str, date_str: str):
    """
    Returns a set of already booked times (HH:MM) for a specific date.
    Example date_str: '2025-11-29'
    """
    try:
        response = (
            supabase.table("appointments")
            .select("scheduled_time")
            .eq("client_id", client_id)
            .gte("scheduled_time", f"{date_str}T00:00:00")
            .lt("scheduled_time", f"{date_str}T23:59:59")
            .execute()
        )

        if not response or not response.data:
            return set()

        booked = set()
        for item in response.data:
            ts = item.get("scheduled_time")  # "2025-11-29T09:00:00+00:00"
            if not ts:
                continue

            # Extract HH:MM
            try:
                time_part = ts.split("T")[1][:5]
                booked.add(time_part)
            except:
                continue

        return booked

    except Exception:
        # Fail-safe: nunca bloquear el sistema
        return set()
