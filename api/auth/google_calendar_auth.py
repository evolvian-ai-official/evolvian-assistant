from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging
import base64
import json
from urllib.parse import urlencode

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
    env = os.getenv("ENV", "").strip().lower()
    host = _request_host(request)
    dynamic_uri = _build_callback_from_request(request)

    # Prefer explicit prod in non-local hosts even if ENV is misconfigured.
    if not _is_local_host(host):
        return dynamic_uri or prod_uri or local_uri
    if env == "prod":
        return dynamic_uri or prod_uri or local_uri
    return local_uri or dynamic_uri or prod_uri


def _encode_state(client_id: str, return_to: str | None) -> str:
    payload = {"client_id": client_id}
    if return_to:
        payload["return_to"] = return_to
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

@router.get("/api/auth/google_calendar/init")
def google_calendar_init(request: Request):
    client_id_param = request.query_params.get("client_id")
    if not client_id_param:
        raise HTTPException(status_code=400, detail="Falta client_id")
    return_to = request.query_params.get("return_to")

    redirect_uri = _resolve_redirect_uri(request)
    if not GOOGLE_CLIENT_ID or not redirect_uri:
        raise HTTPException(status_code=500, detail="Missing Google OAuth configuration")

    logger.info(f"🔍 GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID}")
    logger.info(f"➡️ redirect_uri usado: {redirect_uri}")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "state": _encode_state(client_id_param, return_to),
        "access_type": "offline",
        "prompt": "select_account consent",
    }

    full_url = f"{auth_url}?{urlencode(params)}"
    logger.info(f"🔗 authUrl final: {full_url}")
    logger.info(f"🔗 Redirigiendo a URL de Google: {full_url}")
    return RedirectResponse(full_url)
