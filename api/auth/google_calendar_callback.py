from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
import requests
from urllib.parse import urlencode
from urllib.parse import urlparse
from datetime import datetime, timedelta
from ..modules.assistant_rag.supabase_client import supabase
from api.oauth_state import decode_signed_state
from api.utils.calendar_feature_flags import client_can_use_google_calendar_sync

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
    forced_uri = os.getenv("GOOGLE_REDIRECT_URI_FORCE")
    host = _request_host(request)
    dynamic_uri = _build_callback_from_request(request)

    if forced_uri:
        return forced_uri

    def _host_of(uri: str | None) -> str:
        if not uri:
            return ""
        return (urlparse(uri).hostname or "").lower()

    if not _is_local_host(host):
        for candidate in (prod_uri, dynamic_uri, local_uri):
            if candidate and _host_of(candidate) == host:
                return candidate
        return dynamic_uri or prod_uri or local_uri
    return local_uri or dynamic_uri or prod_uri


def _allowed_google_redirect_uris(request: Request) -> set[str]:
    allowed = {
        (os.getenv("GOOGLE_REDIRECT_URI_LOCAL") or "").strip(),
        (os.getenv("GOOGLE_REDIRECT_URI_PROD") or "").strip(),
        (_build_callback_from_request(request) or "").strip(),
    }
    return {uri for uri in allowed if uri}


def _resolve_token_exchange_redirect_uri(request: Request, state_payload: dict) -> str | None:
    """
    Token exchange must use the exact redirect_uri sent on OAuth init.
    Use signed state value when it is an allowed callback URI.
    """
    expected_redirect_uri = _resolve_redirect_uri(request)
    oauth_redirect_uri = str(state_payload.get("oauth_redirect_uri") or "").strip()
    if oauth_redirect_uri and oauth_redirect_uri in _allowed_google_redirect_uris(request):
        return oauth_redirect_uri
    return expected_redirect_uri


def _resolve_dashboard_redirect(request: Request) -> str:
    local_url = os.getenv("DASHBOARD_REDIRECT_URL_LOCAL", "http://localhost:5173/dashboard")
    prod_url = os.getenv("DASHBOARD_REDIRECT_URL_PROD", "https://evolvianai.net/dashboard")
    host = _request_host(request)
    if not _is_local_host(host):
        return prod_url
    return local_url


def _allowed_return_hosts(request: Request) -> set[str]:
    hosts = {_request_host(request)}
    for env_key in ("DASHBOARD_REDIRECT_URL_LOCAL", "DASHBOARD_REDIRECT_URL_PROD"):
        parsed = urlparse((os.getenv(env_key) or "").strip())
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _sanitize_return_to(request: Request, return_to: str | None) -> str | None:
    if not return_to:
        return None

    parsed = urlparse(return_to)
    if not parsed.scheme and not parsed.netloc:
        # Relative URL on same host.
        return return_to if return_to.startswith("/") else None

    hostname = (parsed.hostname or "").lower()
    if hostname and hostname in _allowed_return_hosts(request):
        return return_to
    return None


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

    try:
        max_age = int(os.getenv("GOOGLE_OAUTH_STATE_TTL_SECONDS", "900"))
        state_payload = decode_signed_state(state, max_age_seconds=max_age)
    except HTTPException:
        return _redirect_with_status(default_dashboard, success=False, reason="invalid_oauth_state")

    client_id = str(state_payload.get("client_id") or "")
    return_to = _sanitize_return_to(request, state_payload.get("return_to"))
    dashboard_redirect_url = return_to or default_dashboard

    google_redirect_uri = _resolve_token_exchange_redirect_uri(request, state_payload)
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not google_redirect_uri or not client_id:
        logging.error("❌ Missing Google OAuth configuration or client_id")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="oauth_config_missing")
    if not client_can_use_google_calendar_sync(client_id):
        logging.warning("🚫 Google Calendar sync blocked by plan | client_id=%s", client_id)
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="feature_not_enabled")

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

    if token_resp.status_code != 200:
        logging.error(
            "❌ Failed to get Google token | status=%s | body=%s",
            token_resp.status_code,
            token_resp.text[:500],
        )
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
        logging.error("❌ Error retrieving calendar list")
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

        supabase.table("calendar_integrations").upsert(data, on_conflict="client_id").execute()
        logging.info(f"✅ Calendar tokens saved successfully for client {client_id}")
    except Exception:
        logging.exception("❌ Failed to save tokens to Supabase")
        return _redirect_with_status(dashboard_redirect_url, success=False, reason="save_calendar_integration_failed")

    # ✅ Redirect to dashboard after success
    final_url = f"{dashboard_redirect_url}{'&' if '?' in dashboard_redirect_url else '?'}connected_calendar=true"
    logging.info(f"✅ Redirecting to: {final_url}")
    return RedirectResponse(url=final_url)
