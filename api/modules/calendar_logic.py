import os
import logging
import datetime
import pytz
import requests
from zoneinfo import ZoneInfo
from datetime import timedelta
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.calendar.schedule_event import schedule_event
from api.modules.calendar.send_confirmation_email import send_confirmation_email
from api.modules.calendar.notify_business_owner import notify_business_owner

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


# ============================================================
# 🔄 Refrescar token de acceso si expiró
# ============================================================
def refresh_access_token(refresh_token: str, client_id: str) -> str:
    try:
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

        # Guardar nuevo token + expiración estimada
        supabase.table("calendar_integrations").update({
            "access_token": new_access_token,
            "expires_at": (datetime.datetime.utcnow() + timedelta(hours=1)).isoformat()
        }).eq("client_id", client_id).execute()

        logger.info("✅ Token actualizado correctamente en Supabase")
        return new_access_token

    except Exception as e:
        logger.exception("❌ Error al refrescar access_token")
        raise


# ============================================================
# 📅 Consultar disponibilidad desde Google Calendar
# ============================================================
def get_availability_from_google_calendar(client_id: str, days_ahead: int = 7) -> dict:
    try:
        logger.info(f"📅 Verificando disponibilidad real para client_id: {client_id}")
        tz = pytz.timezone("America/Mexico_City")
        now = datetime.datetime.now(tz)
        end_range = now + timedelta(days=days_ahead)

        # Buscar integración activa
        resp = (
            supabase.table("calendar_integrations")
            .select("access_token, refresh_token, calendar_id")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        data = resp.data if resp else None
        if not data:
            # Fallback: si no hay integración, usar configuración manual
            manual = (
                supabase.table("client_schedule_settings")
                .select("*")
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            )
            if not manual.data:
                return {"available_slots": [], "message": "❌ No se encontró integración ni horario manual"}
            config = manual.data
            start_hour = int(config.get("availability_start", 9))
            end_hour = int(config.get("availability_end", 18))
            working_days = config.get("working_days", [1, 2, 3, 4, 5])
            available_slots = []
            for d in range(days_ahead):
                day = now + timedelta(days=d)
                if day.isoweekday() in working_days:
                    for hour in range(start_hour, end_hour):
                        slot = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                        available_slots.append(slot.isoformat())
            return {"available_slots": available_slots[:10], "message": "🕒 Horarios manuales generados"}

        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        calendar_id = data["calendar_id"]

        def fetch_busy_times(token):
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            body = {
                "timeMin": now.isoformat(),
                "timeMax": end_range.isoformat(),
                "timeZone": "America/Mexico_City",
                "items": [{"id": calendar_id}]
            }
            return requests.post("https://www.googleapis.com/calendar/v3/freeBusy", headers=headers, json=body)

        res = fetch_busy_times(access_token)

        if res.status_code == 401:
            logger.warning("⚠️ Token expirado. Intentando refrescar...")
            access_token = refresh_access_token(refresh_token, client_id)
            res = fetch_busy_times(access_token)

        res.raise_for_status()
        busy = res.json()["calendars"][calendar_id]["busy"]

        busy_ranges = [
            (
                datetime.datetime.fromisoformat(b["start"]).astimezone(tz),
                datetime.datetime.fromisoformat(b["end"]).astimezone(tz)
            )
            for b in busy
        ]

        available_slots = []
        current = now.replace(minute=0, second=0, microsecond=0)
        slot_duration = timedelta(minutes=30)

        while current < end_range:
            if 9 <= current.hour < 18:
                if not any(start <= current < end for start, end in busy_ranges):
                    available_slots.append({
                        "utc": current.astimezone(ZoneInfo("UTC")).isoformat(),
                        "local": current.isoformat(),
                        "display": current.strftime("%A %d %B, %I:%M %p")
                    })
            current += slot_duration

        logger.info(f"✅ {len(available_slots)} horarios disponibles encontrados.")
        return {"available_slots": available_slots[:10], "message": "Horarios disponibles generados"}

    except Exception as e:
        logger.exception("❌ Error al consultar disponibilidad en Google Calendar")
        return {"available_slots": [], "message": f"Error al consultar disponibilidad: {str(e)}"}


# ============================================================
# 📆 Guardar cita validando disponibilidad
# ============================================================
def save_appointment_if_valid(client_id: str, scheduled_time_str: str, user_email: str = "invitado@evolvian.com", user_name: str = "Invitado", user_phone: str = None, session_id: str = None, channel: str = "chat") -> str:
    try:
        # Convertir a UTC
        scheduled_time_local = datetime.datetime.fromisoformat(scheduled_time_str)
        scheduled_time_utc = scheduled_time_local.astimezone(ZoneInfo("UTC"))
        logger.info(f"🕓 Hora UTC convertida: {scheduled_time_utc.isoformat()}")

        # Prevenir duplicados
        start_window = scheduled_time_utc.isoformat()
        end_window = (scheduled_time_utc + timedelta(minutes=1)).isoformat()
        res = (
            supabase.table("appointments")
            .select("id")
            .eq("client_id", client_id)
            .gte("scheduled_time", start_window)
            .lt("scheduled_time", end_window)
            .execute()
        )
        if res and res.data:
            return "⛔ Ese horario ya está ocupado. Elige otro, por favor."

        # Obtener email de empresa
        client_data = (
            supabase.table("clients")
            .select("user_id")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        user_id = client_data.data["user_id"] if client_data.data else None
        if not user_id:
            return "❌ No se encontró el propietario de esta cuenta."

        user_data = (
            supabase.table("users")
            .select("email")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        empresa_email = user_data.data["email"] if user_data.data else None

        # Insertar cita en Supabase
        appointment_data = {
            "client_id": client_id,
            "user_email": user_email,
            "user_name": user_name,
            "user_phone": user_phone,
            "scheduled_time": scheduled_time_utc.isoformat(),
            "channel": channel,
            "session_id": session_id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        supabase.table("appointments").insert(appointment_data).execute()
        logger.info(f"💾 Cita guardada en Supabase: {appointment_data}")

        # Crear evento en Google Calendar
        schedule_event({
            "client_id": client_id,
            "start": scheduled_time_utc.isoformat(),
            "user_email": user_email,
            "user_name": user_name
        })
        logger.info("📤 Evento enviado a Google Calendar")

        # Formatear hora local
        local_time = scheduled_time_local.astimezone(ZoneInfo("America/Mexico_City"))
        date_str = local_time.strftime("%-d de %B de %Y")
        hour_str = local_time.strftime("%I:%M %p").lstrip("0")

        # Notificar empresa
        notify_business_owner(
            empresa_email=empresa_email,
            slot_time=f"{date_str} a las {hour_str}",
            user_email=user_email,
            user_name=user_name
        )

        # Confirmar usuario
        send_confirmation_email(
            to_email=user_email,
            date_str=date_str,
            hour_str=hour_str
        )

        return f"✅ ¡Cita agendada para {scheduled_time_local.strftime('%Y-%m-%d %H:%M')}!"

    except Exception as e:
        logger.exception("❌ Error al guardar la cita")
        return "❌ Ocurrió un error inesperado. Intenta más tarde."
