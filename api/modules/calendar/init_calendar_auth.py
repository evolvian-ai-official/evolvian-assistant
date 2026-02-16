from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
import os
import urllib.parse
import logging
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(tags=["Calendar"])

# ✅ Real Google Calendar OAuth initializer
@router.get("/auth/google_calendar/init")
def google_calendar_init(
    client_id: str,
    request: Request,
    as_json: bool = Query(False),
):
    authorize_client_request(request, client_id)
    ENV = os.getenv("ENV", "local").lower()
    IS_PROD = ENV == "prod"

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI_PROD" if IS_PROD else "GOOGLE_REDIRECT_URI_LOCAL")

    if not GOOGLE_CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Missing environment variables for Google OAuth")

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

    logging.info(f"🔗 Redirecting to Google Auth URL: {auth_url}")
    if as_json:
        return JSONResponse({"auth_url": auth_url})
    return RedirectResponse(auth_url)


# ✅ Alias route for compatibility with the frontend
@router.get("/calendar/connect")
def alias_calendar_connect(request: Request, client_id: str = Query(...)):
    """
    Alias route for frontend compatibility.
    Redirects to /auth/google_calendar/init so the button URL stays the same.
    """
    try:
        authorize_client_request(request, client_id)
        target_url = f"/auth/google_calendar/init?client_id={client_id}"
        logging.info(f"🔄 Redirecting alias /calendar/connect → {target_url}")
        return RedirectResponse(url=target_url)
    except Exception as e:
        logging.error(f"❌ Error redirecting to Google Calendar auth: {e}")
        return {"error": str(e)}

# ✅ Disconnect Google Calendar
@router.post("/auth/google_calendar/disconnect")
def disconnect_google_calendar(request: Request, client_id: str = Query(...)):
    """
    Deactivates Google Calendar integration for a client in Supabase.
    Used by frontend to 'disconnect' the account.
    """
    try:
        authorize_client_request(request, client_id)
        # Buscar integración activa
        res = (
            supabase.table("calendar_integrations")
            .select("id")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
        )

        if not res or not res.data:
            logging.warning(f"⚠️ No active integration found for {client_id}")
            raise HTTPException(status_code=404, detail="No active Google Calendar integration found")

        integration_id = res.data[0]["id"]

        # Desactivar la integración
        update_res = (
            supabase.table("calendar_integrations")
            .update({
                "is_active": False,
                "connected_email": None,
            })
            .eq("id", integration_id)
            .execute()
        )

        logging.info(f"🧹 Google Calendar disconnected for {client_id}")
        return {"success": True, "message": "Google Calendar disconnected successfully"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"❌ Error disconnecting Google Calendar for {client_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
