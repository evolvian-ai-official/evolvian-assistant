from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
import os, requests, logging
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.calendar.send_confirmation_email import send_confirmation_email
from api.modules.calendar.notify_business_owner import notify_business_owner
from api.modules.calendar_logic import get_availability_from_google_calendar as get_availability

router = APIRouter()
logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# =====================================================
# 🗓️ POST — Crear cita (Supabase + Google Calendar + Email Resend)
# =====================================================
@router.post("/calendar/book")
async def book_calendar(request: Request):
    """
    📅 Crea una cita, sincroniza con Google Calendar y envía correos de confirmación.
    """
    try:
        payload = await request.json()
        logger.info(f"📩 Received book_calendar request: {payload}")

        client_id = payload.get("client_id")
        user_email = payload.get("user_email")
        user_name = payload.get("user_name")
        scheduled_time = datetime.fromisoformat(payload.get("scheduled_time"))

        # =====================================
        # 1️⃣ Guardar cita en Supabase
        # =====================================
        try:
            res = (
                supabase.table("appointments")
                .insert({
                    "client_id": client_id,
                    "user_email": user_email,
                    "user_name": user_name,
                    "scheduled_time": scheduled_time.isoformat(),
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "confirmed",
                    "channel": "chat",
                })
                .execute()
            )
            logger.info(f"✅ Appointment saved in Supabase: {res.data}")
        except Exception as db_err:
            logger.exception("❌ Error saving appointment in Supabase")
            return JSONResponse(
                content={"success": False, "error": f"Database error: {db_err}"},
                status_code=500,
            )

        # =====================================
        # 2️⃣ Google Calendar Sync (con refresh token)
        # =====================================
        try:
            integration = (
                supabase.table("calendar_integrations")
                .select("access_token, refresh_token, calendar_id, is_active, connected_email, expires_at")
                .eq("client_id", client_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )

            if integration and integration.data:
                record = integration.data[0]
                access_token = record.get("access_token")
                refresh_token = record.get("refresh_token")
                calendar_id = record.get("calendar_id")
                connected_email = record.get("connected_email")
                expires_at = record.get("expires_at")

                # ✅ Refresh token if expired
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if expires_dt.tzinfo is not None:
                            expires_dt = expires_dt.astimezone(timezone.utc).replace(tzinfo=None)

                        if expires_dt < datetime.utcnow():
                            logger.info("♻️ Access token expired — refreshing...")
                            refresh_res = requests.post(
                                GOOGLE_TOKEN_URL,
                                data={
                                    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                                    "refresh_token": refresh_token,
                                    "grant_type": "refresh_token",
                                },
                                timeout=10,
                            )
                            if refresh_res.status_code == 200:
                                new_token = refresh_res.json().get("access_token")
                                access_token = new_token
                                supabase.table("calendar_integrations").update({
                                    "access_token": new_token,
                                    "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
                                }).eq("client_id", client_id).execute()
                                logger.info("✅ Google token refreshed and saved.")
                            else:
                                logger.warning(f"⚠️ Failed to refresh token: {refresh_res.text}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error parsing or refreshing token expiration: {e}")

                if access_token and calendar_id:
                    event = {
                        "summary": f"Cita con {user_name}",
                        "description": f"Agendada por Evolvian AI — {user_email}",
                        "start": {"dateTime": scheduled_time.isoformat(), "timeZone": "UTC"},
                        "end": {
                            "dateTime": (scheduled_time + timedelta(minutes=30)).isoformat(),
                            "timeZone": "UTC",
                        },
                    }

                    gcal_response = requests.post(
                        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=event,
                        timeout=10,
                    )

                    if gcal_response.status_code in [200, 201]:
                        logger.info("✅ Event created in Google Calendar")
                    else:
                        logger.warning(f"⚠️ Google Calendar sync failed: {gcal_response.text}")
                else:
                    logger.warning("⚠️ Missing calendar_id or access_token — skipping sync.")
            else:
                logger.info("ℹ️ No active Google Calendar integration for this client.")
        except Exception as sync_error:
            logger.warning(f"⚠️ Error syncing Google Calendar: {sync_error}")

        # =====================================
        # 3️⃣ Enviar correos (usuario + negocio)
        # =====================================
        try:
            date_str = scheduled_time.strftime("%Y-%m-%d")
            hour_str = scheduled_time.strftime("%H:%M")

            # ✉️ Confirmación al usuario
            send_confirmation_email(user_email, date_str, hour_str)
            logger.info(f"📨 Confirmation email sent to {user_email}")

            # ✉️ Notificación al negocio (usa client_id internamente)
            try:
                notify_business_owner(client_id, f"{date_str} {hour_str}", user_email, user_name)
                logger.info(f"📨 Business owner notified for client_id={client_id}")
            except Exception as e:
                logger.warning(f"⚠️ Error notifying business owner: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Error sending emails: {e}")

        # =====================================
        # 4️⃣ Respuesta final
        # =====================================
        logger.info(f"🎉 Appointment confirmed for {user_name} ({user_email}) at {scheduled_time}")
        return JSONResponse(
            content={"success": True, "message": "Appointment created successfully"},
            status_code=200,
        )

    except Exception as e:
        logger.exception("❌ Error creating appointment")
        return JSONResponse(
            content={"success": False, "error": str(e)}, status_code=500
        )
