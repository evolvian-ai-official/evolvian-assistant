from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import urllib.parse
import logging

router = APIRouter()

@router.get("/auth/google_calendar/init")
def google_calendar_init(client_id: str, request: Request):
    ENV = os.getenv("ENV", "local").lower()
    IS_PROD = ENV == "prod"

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI_PROD" if IS_PROD else "GOOGLE_REDIRECT_URI_LOCAL")

    if not GOOGLE_CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Faltan variables de entorno")

    scopes = ["https://www.googleapis.com/auth/calendar"]
    scope_param = urllib.parse.quote(" ".join(scopes), safe="")
    redirect_uri_param = urllib.parse.quote(REDIRECT_URI, safe="")
    state = urllib.parse.quote(client_id, safe="")

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri_param}"
        "&response_type=code"
        f"&scope={scope_param}"
        f"&state={state}"
        "&access_type=offline"
        "&prompt=select_account%20consent"
    )

    logging.info(f"🔗 Redirigiendo a Google Auth URL: {auth_url}")
    return RedirectResponse(auth_url)
