from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
import requests
import base64
import json
from urllib.parse import urlencode
from datetime import datetime, timedelta
from ..modules.assistant_rag.supabase_client import supabase

# ✅ Prefijo /api para que coincida con las rutas del frontend
router = APIRouter(prefix="/api", tags=["Calendar"])

# 🌍 Configuración por entorno
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


def _request_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        return forwarded.split(",")[0].strip().lower()
    return (request.url.hostname or "").lower()


def _is_local_host(host: str) -> bool:
    return host in {"localhost", "127.0.0.1"} or host.endswith(".local")


def _resolve_redirect_uri(request: Request) -> str | None:
    local_uri = os.getenv("GOOGLE_REDIRECT_URI_LOCAL")
    prod_uri = os.getenv("GOOGLE_REDIRECT_URI_PROD")
    host = _request_host(request)
    if not _is_local_host(host):
        return prod_uri or local_uri
    return local_uri or prod_uri


def _resolve_dashboard_redirect(request: Request) -> str:
    local_url = os.getenv("DASHBOARD_REDIRECT_URL_LOCAL", "http://localhost:5173/dashboard")
    prod_url = os.getenv("DASHBOARD_REDIRECT_URL_PROD", "https://evolvianai.net/dashboard")
    host = _request_host(request)
    if not _is_local_host(host):
        return prod_url
    return local_url


def _decode_state(raw_state: str) -> tuple[str, str | None]:
    """
    Backward compatible:
    - New format: base64url(JSON) {"client_id":"...","return_to":"..."}
    - Legacy format: plain client_id string
    """
    if not raw_state:
        return "", None

    try:
        padded = raw_state + "=" * (-len(raw_state) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
        if isinstance(payload, dict) and payload.get("client_id"):
            return str(payload.get("client_id")), payload.get("return_to")
    except Exception:
        pass

    return raw_state, None


def _redirect_with_status(base_url: str, success: bool, reason: str | None = None):
    query = {"connected_calendar": "true" if success else "false"}
    if reason:
        query["calendar_error"] = reason
    sep = "&" if "?" in base_url else "?"
    return RedirectResponse(url=f"{base_url}{sep}{urlencode(query)}")


@router.get("/auth/google_calendar/callback")
async def google_calendar_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """
    Handles Google's OAuth2 callback for Evolvian Calendar integration.
    Exchanges the authorization code for tokens and saves them in Supabase.
    """
    default_dashboard = _resolve_dashboard_redirect(request)

    if error:
        logging.error(f"❌ Google auth error: {error}")
        return _redirect_with_status(default_dashboard, success=False, reason="google_oauth_error")

    if not code or not state:
        return _redirect_with_status(default_dashboard, success=False, reason="missing_callback_params")

    client_id, return_to = _decode_state(state)
    dashboard_redirect_url = return_to or default_dashboard
    google_redirect_uri = _resolve_redirect_uri(request)
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not google_redirect_uri or not client_id:
        logging.error("❌ Missing Google OAuth configuration or client_id")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="oauth_config_missing")

    logging.info(f"🔄 Received callback | client_id={client_id} | code_present={bool(code)}")
    logging.info(f"➡️ redirect_uri used: {google_redirect_uri}")

    # 📨 Exchange authorization code for access + refresh tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": google_redirect_uri,
        "grant_type": "authorization_code",
    }

    logging.info(
        "📤 Token exchange payload (safe): %s",
        {
            "code_present": bool(code),
            "client_id_present": bool(GOOGLE_CLIENT_ID),
            "client_secret_present": bool(GOOGLE_CLIENT_SECRET),
            "redirect_uri": google_redirect_uri,
            "grant_type": token_data.get("grant_type"),
        },
    )
    try:
        token_resp = requests.post(token_url, data=token_data, timeout=20)
    except Exception:
        logging.exception("❌ Token exchange network error")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="token_exchange_network_error")

    logging.info(f"📥 Token exchange status: {token_resp.status_code}")
    logging.info(f"📥 Token exchange response: {token_resp.text}")

    if token_resp.status_code != 200:
        logging.error(f"❌ Failed to get Google token: {token_resp.text}")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="token_exchange_failed")

    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in")

    if not access_token:
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="missing_access_token")

    # 📅 Fetch user’s primary calendar
    try:
        calendar_resp = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except Exception:
        logging.exception("❌ Failed to call Google Calendar API")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="google_calendar_api_error")

    if calendar_resp.status_code != 200:
        logging.error(f"❌ Error retrieving calendar list: {calendar_resp.text}")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="calendar_list_failed")

    calendars = calendar_resp.json().get("items", [])
    if not calendars:
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="no_calendars_found")

    primary_calendar = next((c for c in calendars if c.get("primary")), calendars[0])
    calendar_id = primary_calendar["id"]
    connected_email = primary_calendar.get("summaryOverride") or primary_calendar.get("summary") or ""

    # 💾 Save tokens and calendar info into Supabase
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in or 3600))

        # Google can omit refresh_token on re-consent. Preserve existing value in that case.
        if not refresh_token:
            existing = (
                supabase.table("calendar_integrations")
                .select("refresh_token")
                .eq("client_id", client_id)
                .limit(1)
                .execute()
            )
            if existing and existing.data:
                refresh_token = existing.data[0].get("refresh_token")

        data = {
            "client_id": client_id,
            "provider": "google",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "calendar_id": calendar_id,
            "timezone": primary_calendar.get("timeZone", "UTC"),
            "connected_email": connected_email,
            "connected_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_active": True,
        }

        logging.info(f"💾 Saving calendar integration: {data}")
        supabase.table("calendar_integrations").upsert(data, on_conflict="client_id").execute()
        logging.info(f"✅ Calendar tokens saved successfully for client {client_id}")
    except Exception:
        logging.exception("❌ Failed to save tokens to Supabase")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="save_calendar_integration_failed")

    # ✅ Redirect to dashboard after success
    final_url = f"{dashboard_redirect_url}{'&' if '?' in dashboard_redirect_url else '?'}connected_calendar=true"
    logging.info(f"✅ Redirecting to: {final_url}")
    return RedirectResponse(url=final_url)
