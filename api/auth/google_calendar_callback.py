from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
import requests
from datetime import datetime, timedelta
from ..modules.assistant_rag.supabase_client import supabase

router = APIRouter()

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
    os.getenv("DASHBOARD_REDIRECT_URL_PROD", "https://evolvianai.com/dashboard")
    if ENV == "prod"
    else os.getenv("DASHBOARD_REDIRECT_URL_LOCAL", "http://localhost:5173/dashboard")
)

@router.get("/auth/google_calendar/callback")
async def google_calendar_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        logging.error(f"❌ Error al autenticar con Google: {error}")
        raise HTTPException(status_code=400, detail="Error en la autenticación con Google")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Faltan parámetros en la URL")

    client_id = state
    logging.info(f"🔄 Recibido callback con client_id={client_id} y código={code}")
    logging.info(f"🌐 ENV: {ENV}")
    logging.info(f"➡️ redirect_uri usado: {GOOGLE_REDIRECT_URI}")

    # 📨 Intercambio del código por tokens
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
        logging.error(f"❌ Error al obtener token: {token_resp.text}")
        raise HTTPException(status_code=500, detail="Error al obtener token de Google")

    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in")

    if not access_token:
        raise HTTPException(status_code=500, detail="No se recibió access_token")

    # 📅 Obtener calendario principal del usuario
    calendar_resp = requests.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if calendar_resp.status_code != 200:
        logging.error(f"❌ Error al obtener lista de calendarios: {calendar_resp.text}")
        raise HTTPException(status_code=500, detail="No se pudo obtener lista de calendarios")

    calendars = calendar_resp.json().get("items", [])
    if not calendars:
        raise HTTPException(status_code=500, detail="No se encontraron calendarios en la cuenta de Google")

    primary_calendar = next((c for c in calendars if c.get("primary")), calendars[0])
    calendar_id = primary_calendar["id"]

    # 💾 Guardar tokens e información en Supabase
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
            "expires_at": expires_at.isoformat()
        }

        logging.info(f"💾 Guardando integración calendar: {data}")
        supabase.table("calendar_integrations").upsert(data, on_conflict="client_id").execute()
    except Exception as e:
        logging.exception("❌ Error al guardar tokens en Supabase")
        raise HTTPException(status_code=500, detail="Error al guardar integración en Supabase")

    # ✅ Redirección dinámica
    final_url = f"{DASHBOARD_REDIRECT_URL}?connected_calendar=true"
    logging.info(f"✅ Redirigiendo a: {final_url}")
    return RedirectResponse(url=final_url)
