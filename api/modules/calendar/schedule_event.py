from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import requests, os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

@router.post("/schedule_event")
def schedule_event(payload: dict):
    client_id = payload["client_id"]
    slot_time = payload["start"]
    user_email = payload["user_email"]
    user_name = payload.get("user_name", "Cliente Evolvian")

    print(f"📅 Agendando evento para client_id={client_id} en horario={slot_time}...")

    # Obtener integración de calendario
    integration = supabase.table("calendar_integrations").select("*").eq("client_id", client_id).maybe_single().execute().data
    if not integration:
        raise HTTPException(404, "No calendar connected")

    access_token = integration["access_token"]
    calendar_id = integration["calendar_id"] or "primary"
    timezone = integration.get("timezone") or "UTC"

    # Validar formato de slot_time
    try:
        start_dt = datetime.fromisoformat(slot_time)
    except Exception as e:
        print("❌ Error parsing slot_time:", e)
        raise HTTPException(400, "Invalid datetime format")

    # Crear evento en Google Calendar
    event_data = {
        "summary": "Sesión agendada desde Evolvian",
        "description": f"Llamada con {user_name}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": (start_dt + timedelta(minutes=30)).isoformat(), "timeZone": timezone},
        "attendees": [{"email": user_email}],
        "reminders": {"useDefault": True},
    }

    res = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=event_data,
    )

    if res.status_code >= 400:
        print(f"❌ Error al crear evento en Google Calendar: {res.status_code} - {res.text}")
        raise HTTPException(res.status_code, "Error creating event")

    event = res.json()

    # Guardar cita en Supabase
    try:
        supabase.table("appointments").insert({
            "client_id": client_id,
            "user_email": user_email,
            "user_name": user_name,
            "scheduled_time": slot_time,
            "calendar_event_id": event["id"],
            "email_sent": False,
        }).execute()
    except Exception as e:
        print("⚠️ Error guardando cita en Supabase:", e)

    # Enviar email de confirmación
    try:
        sg = SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        message = Mail(
            from_email="no-reply@evolvian.com",
            to_emails=user_email,
            subject="✅ Tu cita ha sido agendada",
            html_content=f"""
            <p>Hola {user_name},</p>
            <p>Tu cita ha sido confirmada para:</p>
            <p><strong>{slot_time}</strong></p>
            <p>Gracias por usar el asistente de Evolvian.</p>
            <p>📅 Nos vemos pronto.</p>
            """
        )
        sg.send(message)

        # Actualizar estado del email
        supabase.table("appointments").update({"email_sent": True}).eq("calendar_event_id", event["id"]).execute()
    except Exception as e:
        print("❌ Error al enviar email de confirmación:", e)

    return {"status": "scheduled", "event": event}
