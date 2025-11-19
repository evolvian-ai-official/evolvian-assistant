import os
import logging
from datetime import datetime, timedelta
import requests
from fastapi import APIRouter, HTTPException
from supabase import create_client
from dotenv import load_dotenv

# ============================================================
# 🔧 Configuración
# ============================================================
load_dotenv()
router = APIRouter(tags=["Calendar"])
logger = logging.getLogger("schedule_event")

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


# ============================================================
# 🔄 Refrescar token de Google si expira
# ============================================================
def refresh_access_token(client_id: str, refresh_token: str) -> str:
    logger.info("🔄 Refreshing Google Calendar access token...")
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        logger.error(f"❌ Failed to refresh token: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to refresh Google token")

    new_token = response.json().get("access_token")
    if not new_token:
        raise HTTPException(status_code=500, detail="No access_token returned from Google")

    supabase.table("calendar_integrations").update({
        "access_token": new_token,
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }).eq("client_id", client_id).execute()

    logger.info("✅ Token refreshed and saved in Supabase")
    return new_token


# ============================================================
# 📅 Agendar evento en Google Calendar
# ============================================================
@router.post("/schedule_event")
def schedule_event(payload: dict):
    """
    Creates a new event in Google Calendar and stores it in Supabase.
    """
    try:
        client_id = payload["client_id"]
        slot_time = payload["start"]
        user_email = payload.get("user_email")
        user_name = payload.get("user_name", "Cliente Evolvian")

        logger.info(f"📅 Scheduling event for client_id={client_id} at {slot_time}")

        # 1️⃣ Get calendar integration
        integration_resp = (
            supabase.table("calendar_integrations")
            .select("*")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        integration = integration_resp.data
        if not integration:
            raise HTTPException(status_code=404, detail="No calendar connected")

        access_token = integration["access_token"]
        refresh_token = integration.get("refresh_token")
        calendar_id = integration.get("calendar_id") or "primary"
        timezone = integration.get("timezone") or "UTC"
        owner_email = integration.get("connected_email", "owner@evolvian.com")

        # 2️⃣ Validate slot_time format
        try:
            start_dt = datetime.fromisoformat(slot_time)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid datetime format")

        # 3️⃣ Build attendees list safely
        attendees = []
        if user_email:
            attendees.append({"email": user_email})
        else:
            logger.warning("⚠️ Missing user email — event will use fallback attendee.")

        # fallback: use connected_email to avoid 400 error
        if not attendees and owner_email:
            attendees.append({"email": owner_email})
            logger.info(f"📧 Using connected_email as fallback attendee: {owner_email}")

        # ✅ Asegurar que el owner siempre esté como invitado (además del usuario)
        if owner_email and owner_email not in [a["email"] for a in attendees]:
            attendees.append({"email": owner_email})
            logger.info(f"📧 Added owner_email as attendee: {owner_email}")

        # 4️⃣ Prepare event details
        event_data = {
            "summary": f"Sesión agendada con {user_name}",
            "description": f"Evento creado automáticamente desde Evolvian AI para {user_name}.",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": (start_dt + timedelta(minutes=30)).isoformat(), "timeZone": timezone},
            "organizer": {"email": owner_email, "displayName": "Evolvian AI"},
            "attendees": attendees,
            "reminders": {"useDefault": True},
        }

        if attendees:
            event_data["attendees"] = attendees

        # 5️⃣ Create event in Google Calendar
        create_event = requests.post(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            params={"sendUpdates": "all"},
            json=event_data,
        )

        # Retry if token expired
        if create_event.status_code == 401 and refresh_token:
            logger.warning("⚠️ Token expired, refreshing...")
            access_token = refresh_access_token(client_id, refresh_token)
            create_event = requests.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                params={"sendUpdates": "all"},
                json=event_data,
            )

        if create_event.status_code >= 400:
            logger.error(f"❌ Error creating Google event: {create_event.text}")
            raise HTTPException(status_code=create_event.status_code, detail="Error creating event in Google Calendar")

        event = create_event.json()
        logger.info(f"✅ Event created successfully in Google Calendar: {event.get('id')}")

        # 6️⃣ Save in Supabase
        supabase.table("appointments").insert({
            "client_id": client_id,
            "user_email": user_email or owner_email,
            "user_name": user_name,
            "scheduled_time": start_dt.isoformat(),
            "calendar_event_id": event["id"],
            "email_sent": False,
        }).execute()
        logger.info("💾 Appointment saved in Supabase")

        # 7️⃣ Send confirmation email (if SendGrid active)
        if SENDGRID_API_KEY:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email="no-reply@evolvian.com",
                to_emails=user_email or owner_email,
                subject="✅ Your appointment is confirmed",
                html_content=f"""
                    <div style="font-family:sans-serif; color:#222">
                      <h2>Hi {user_name},</h2>
                      <p>Your appointment has been confirmed for:</p>
                      <p><strong>{start_dt.strftime('%A, %B %d %Y at %I:%M %p')}</strong></p>
                      <p>This event has also been added to your Google Calendar.</p>
                      <br/>
                      <p>Thank you for scheduling with <strong>Evolvian AI</strong>.</p>
                    </div>
                """,
            )
            try:
                sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
                sg.send(message)
                supabase.table("appointments").update({"email_sent": True}).eq("calendar_event_id", event["id"]).execute()
                logger.info("📧 Confirmation email sent successfully to user")
            except Exception as e:
                logger.error(f"❌ Error sending confirmation email: {e}")
        else:
            logger.warning("⚠️ SENDGRID_API_KEY not configured, skipping email send")

        return {"status": "scheduled", "event": event}

    except Exception as e:
        logger.exception("❌ Error in schedule_event")
        raise HTTPException(status_code=500, detail=str(e))
