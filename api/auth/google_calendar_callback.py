from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
import requests
from datetime import datetime, timedelta
from ..modules.assistant_rag.supabase_client import supabase

# ✅ Prefijo /api para que coincida con las rutas del frontend
router = APIRouter(prefix="/api", tags=["Calendar"])

# 🌍 Configuración por entorno
ENV = os.getenv("ENV", "local").lower()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = (
    os.getenv("GOOGLE_REDIRECT_URI_PROD")
    if ENV == "prod"
    else os.getenv("GOOGLE_REDIRECT_URI_LOCAL")
)
DASHBOARD_REDIRECT_URL = (
    os.getenv("DASHBOARD_REDIRECT_URL_PROD", "https://evolvianai.net/dashboard")
    if ENV == "prod"
    else os.getenv("DASHBOARD_REDIRECT_URL_LOCAL", "http://localhost:5173/dashboard")
)


@router.get("/auth/google_calendar/callback")
async def google_calendar_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """
    Handles Google's OAuth2 callback for Evolvian Calendar integration.
    Exchanges the authorization code for tokens and saves them in Supabase.
    """
    if error:
        logging.error(f"❌ Google auth error: {error}")
        raise HTTPException(status_code=400, detail="Error during Google authentication")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing required parameters in callback URL")

    client_id = state
    logging.info(f"🔄 Received callback | client_id={client_id} | code={code}")
    logging.info(f"🌐 ENV: {ENV}")
    logging.info(f"➡️ redirect_uri used: {GOOGLE_REDIRECT_URI}")

    # 📨 Exchange authorization code for access + refresh tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
        "is_active": True
    }

    logging.info(f"📤 Token exchange payload: {token_data}")
    token_resp = requests.post(token_url, data=token_data)
    logging.info(f"📥 Token exchange status: {token_resp.status_code}")
    logging.info(f"📥 Token exchange response: {token_resp.text}")

    if token_resp.status_code != 200:
        logging.error(f"❌ Failed to get Google token: {token_resp.text}")
        raise HTTPException(status_code=500, detail="Failed to obtain token from Google")

    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in")

    if not access_token:
        raise HTTPException(status_code=500, detail="Missing access_token from Google response")

    # 📅 Fetch user’s primary calendar
    calendar_resp = requests.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if calendar_resp.status_code != 200:
        logging.error(f"❌ Error retrieving calendar list: {calendar_resp.text}")
        raise HTTPException(status_code=500, detail="Unable to fetch Google Calendars")

    calendars = calendar_resp.json().get("items", [])
    if not calendars:
        raise HTTPException(status_code=500, detail="No calendars found in the Google account")

    primary_calendar = next((c for c in calendars if c.get("primary")), calendars[0])
    calendar_id = primary_calendar["id"]

    # 💾 Save tokens and calendar info into Supabase
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        data = {
            "client_id": client_id,
            "provider": "google",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "calendar_id": calendar_id,
            "timezone": "UTC",
            "connected_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_active": True,
        }

        logging.info(f"💾 Saving calendar integration: {data}")
        supabase.table("calendar_integrations").upsert(data, on_conflict="client_id").execute()
        logging.info(f"✅ Calendar tokens saved successfully for client {client_id}")
    except Exception as e:
        logging.exception("❌ Failed to save tokens to Supabase")
        raise HTTPException(status_code=500, detail="Error saving calendar integration to Supabase")

    # ✅ Redirect to dashboard after success
    final_url = f"{DASHBOARD_REDIRECT_URL}?connected_calendar=true"
    logging.info(f"✅ Redirecting to: {final_url}")
    return RedirectResponse(url=final_url)
