from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
import os
import urllib.parse
import logging
import base64
import json
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(tags=["Calendar"])


def _request_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        return forwarded.split(",")[0].strip().lower()
    return (request.url.hostname or "").lower()


def _request_scheme(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.split(",")[0].strip().lower()
    return (request.url.scheme or "https").lower()


def _is_local_host(host: str) -> bool:
    return host in {"localhost", "127.0.0.1"} or host.endswith(".local")


def _build_callback_from_request(request: Request) -> str | None:
    host = _request_host(request)
    if not host:
        return None
    scheme = _request_scheme(request)
    return f"{scheme}://{host}/api/auth/google_calendar/callback"


def _resolve_redirect_uri(request: Request) -> str | None:
    local_uri = os.getenv("GOOGLE_REDIRECT_URI_LOCAL")
    prod_uri = os.getenv("GOOGLE_REDIRECT_URI_PROD")
    host = _request_host(request)
    dynamic_uri = _build_callback_from_request(request)
    if not _is_local_host(host):
        return dynamic_uri or prod_uri or local_uri
    return local_uri or dynamic_uri or prod_uri


def _encode_state(client_id: str, return_to: str | None) -> str:
    payload = {"client_id": client_id}
    if return_to:
        payload["return_to"] = return_to
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


# ✅ Real Google Calendar OAuth initializer
@router.get("/auth/google_calendar/init")
def google_calendar_init(
    client_id: str,
    request: Request,
    as_json: bool = Query(False),
    return_to: str | None = Query(None),
):
    authorize_client_request(request, client_id)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    REDIRECT_URI = _resolve_redirect_uri(request)

    if not GOOGLE_CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Missing environment variables for Google OAuth")

    scopes = ["https://www.googleapis.com/auth/calendar"]
    scope_param = urllib.parse.quote(" ".join(scopes), safe="")
    redirect_uri_param = urllib.parse.quote(REDIRECT_URI, safe="")
    state = urllib.parse.quote(_encode_state(client_id, return_to), safe="")

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
