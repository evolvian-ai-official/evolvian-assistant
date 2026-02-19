from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import os
import logging
from urllib.parse import urlencode
from urllib.parse import urlparse
from api.authz import authorize_client_request
from api.oauth_state import encode_signed_state

router = APIRouter()

# Configuración y logs
logger = logging.getLogger(__name__)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


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
    env = os.getenv("ENV", "").strip().lower()
    host = _request_host(request)
    dynamic_uri = _build_callback_from_request(request)

    if forced_uri:
        return forced_uri

    def _host_of(uri: str | None) -> str:
        if not uri:
            return ""
        return (urlparse(uri).hostname or "").lower()

    # In production prefer callback URI that matches the request host.
    # This avoids redirecting OAuth callbacks to a frontend-only domain.
    if not _is_local_host(host):
        for candidate in (prod_uri, dynamic_uri, local_uri):
            if candidate and _host_of(candidate) == host:
                return candidate
        return dynamic_uri or prod_uri or local_uri
    if env == "prod":
        return prod_uri or dynamic_uri or local_uri
    return local_uri or dynamic_uri or prod_uri


@router.get("/api/auth/google_calendar/init")
def google_calendar_init(
    request: Request,
    client_id: str,
    return_to: str | None = None,
    as_json: bool = False,
):
    authorize_client_request(request, client_id)

    redirect_uri = _resolve_redirect_uri(request)
    if not GOOGLE_CLIENT_ID or not redirect_uri:
        raise HTTPException(status_code=500, detail="Missing Google OAuth configuration")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    state = encode_signed_state(
        {
            "client_id": client_id,
            "return_to": return_to,
            "oauth_redirect_uri": redirect_uri,
        }
    )

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account consent",
    }

    full_url = f"{auth_url}?{urlencode(params)}"
    if as_json:
        return JSONResponse({"auth_url": full_url})
    return RedirectResponse(full_url)
