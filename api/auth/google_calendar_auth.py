from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
from urllib.parse import urlencode

router = APIRouter()

# Configuración y logs
logger = logging.getLogger(__name__)
ENV = os.getenv("ENV", "local").lower()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

GOOGLE_REDIRECT_URI = (
    os.getenv("GOOGLE_REDIRECT_URI_PROD")
    if ENV == "prod"
    else os.getenv("GOOGLE_REDIRECT_URI_LOCAL")
)

@router.get("/auth/google_calendar/init")
def google_calendar_init(request: Request):
    client_id_param = request.query_params.get("client_id")
    if not client_id_param:
        raise HTTPException(status_code=400, detail="Falta client_id")

    logger.info(f"🌐 ENV: {ENV}")
    logger.info(f"🔍 GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID}")
    logger.info(f"➡️ redirect_uri usado: {GOOGLE_REDIRECT_URI}")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "state": client_id_param,
        "access_type": "offline",
        "prompt": "select_account consent",
    }

    full_url = f"{auth_url}?{urlencode(params)}"
    logger.info(f"🔗 authUrl final: {full_url}")
    logger.info(f"🔗 Redirigiendo a URL de Google: {full_url}")
    return RedirectResponse(full_url)
