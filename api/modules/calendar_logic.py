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
        tz = pytz.timezone("America/Mexico_City")
        now = datetime.datetime.now(tz)
        end_range = now + timedelta(days=days_ahead)

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
            return {"available_slots": [], "message": "❌ No se encontró integración con Google Calendar"}

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
            access_token = refresh_access_token(refresh_token)
            supabase.table("calendar_integrations")\
                .update({"access_token": access_token})\
                .eq("client_id", client_id).execute()
            res = fetch_busy_times(access_token)

        res.raise_for_status()
        busy = res.json()["calendars"][calendar_id]["busy"]

        busy_ranges = [
            (
                datetime.datetime.fromisoformat(b["start"]).astimezone(tz),
                datetime.datetime.fromisoformat(b["end"]).astimezone(tz)
            ) for b in busy
        ]

        available_slots = []
        current = now.replace(minute=0, second=0, microsecond=0)
        slot_duration = timedelta(minutes=30)

        while current < end_range:
            if 9 <= current.hour < 18:
                if not any(start <= current < end for start, end in busy_ranges):
                    available_slots.append(current.isoformat())
            current += slot_duration

        logger.info(f"✅ {len(available_slots)} horarios disponibles encontrados.")
        return {"available_slots": available_slots[:10], "message": "Horarios disponibles generados"}

    except Exception as e:
        logger.exception("❌ Error al consultar disponibilidad en Google Calendar")
        return {"available_slots": [], "message": f"Error al consultar disponibilidad: {str(e)}"}

def save_appointment_if_valid(client_id: str, scheduled_time_str: str) -> str:
    try:
        # 1. Convertir string a datetime con zona horaria correcta
        scheduled_time_local = datetime.datetime.fromisoformat(scheduled_time_str)
        scheduled_time_utc = scheduled_time_local.astimezone(ZoneInfo("UTC"))
        logger.info(f"🕓 Hora en UTC convertida: {scheduled_time_utc.isoformat()}")

        # 2. Definir ventana de 1 minuto para evitar colisiones
        start_window = scheduled_time_utc.isoformat()
        end_window = (scheduled_time_utc + timedelta(minutes=1)).isoformat()

        # 3. Verificar si ya hay cita
        res = (
            supabase.table("appointments")
            .select("id")
            .eq("client_id", client_id)
            .gte("scheduled_time", start_window)
            .lt("scheduled_time", end_window)
            .execute()
        )
        if res and res.data:
            logger.warning(f"⚠️ Ya existe una cita en ese horario: {res.data[0]}")
            return "⛔ Ese horario ya está ocupado. Elige otro, por favor."

        # 4. Obtener user_id desde clients
        client_data = (
            supabase.table("clients")
            .select("user_id")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        user_id = client_data.data["user_id"] if client_data.data else None
        if not user_id:
            logger.error("❌ No se encontró user_id asociado al cliente")
            return "❌ No se encontró el propietario de esta cuenta."

        # 5. Obtener email del usuario (empresa)
        user_data = (
            supabase.table("users")
            .select("email")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        empresa_email = user_data.data["email"] if user_data.data else None
        if not empresa_email:
            logger.error("❌ No se encontró el email del cliente para notificación")
            return "❌ No se pudo encontrar el correo del cliente para enviar la notificación."

        logger.info(f"📨 Email del cliente obtenido: {empresa_email}")

        # 6. Crear evento en Google Calendar
        schedule_event({
            "client_id": client_id,
            "start": scheduled_time_utc.isoformat(),
            "user_email": "invitado@evolvian.com",  # Placeholder para futuro
            "user_name": "Sin nombre"
        })
        logger.info("📤 Evento enviado a Google Calendar")

        # 7. Preparar texto de hora y fecha local
        local_time = scheduled_time_local.astimezone(ZoneInfo("America/Mexico_City"))
        date_str = local_time.strftime("%-d de %B de %Y")
        hour_str = local_time.strftime("%I:%M %p").lstrip("0").replace("AM", "AM").replace("PM", "PM")

        # 8. Notificar a la empresa
        try:
            notify_business_owner(
                empresa_email=empresa_email,
                slot_time=f"{date_str} a las {hour_str}",
                user_email="invitado@evolvian.com",  # Placeholder
                user_name="Sin nombre"
            )
            logger.info("📧 Correo de notificación a empresa enviado")
        except Exception as e:
            logger.error(f"❌ Error al enviar notificación a cliente: {str(e)}")

        # 9. Confirmación al usuario (más adelante será real)
        try:
            send_confirmation_email(
                to_email="invitado@evolvian.com",
                date_str=date_str,
                hour_str=hour_str
            )
            logger.info("📧 Correo de confirmación enviado al usuario")
        except Exception as e:
            logger.error(f"❌ Error al enviar email de confirmación: {str(e)}")

        return f"✅ ¡Cita agendada para {scheduled_time_local.strftime('%Y-%m-%d %H:%M')}!"

    except Exception as e:
        logger.exception("❌ Excepción al guardar la cita:")
        return "❌ Ocurrió un error inesperado. Intenta más tarde."
