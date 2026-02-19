# api/modules/email/gmail_oauth.py
import os
import base64
import time
import socket
from urllib.parse import urlencode
from email.mime.text import MIMEText

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport import requests as google_requests

from api.compliance.email_policy import (
    begin_email_send_audit,
    complete_email_send_audit,
)
from api.compliance.email_marketing_standard import ensure_marketing_footer
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(prefix="/gmail_oauth", tags=["Gmail OAuth"])

# =====================================================
# 📧 Evolvian AI — Gmail OAuth (Render-Optimized)
# =====================================================

# Timeout global (Render bloquea sockets lentos)
socket.setdefaulttimeout(10)

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "https://evolvianai.com/gmail_oauth/callback")
WORKSPACE_MODE = os.getenv("WORKSPACE_MODE", "false").lower() == "true"

# Usar un único scope "full" evita inconsistencias (cubre read/send/modify)
SCOPES = ["https://mail.google.com/"]

# Escopes extra SOLO si realmente los necesitas en modo workspace
if WORKSPACE_MODE:
    SCOPES += [
        "https://www.googleapis.com/auth/gmail.labels",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.addons.current.message.action",
        "https://www.googleapis.com/auth/gmail.addons.current.action.compose",
    ]


def _ui_email_setup_url(request: Request, extra_query: dict | None = None) -> str:
    host = (request.url.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1"}
    base = "http://localhost:4223/services/email" if is_local else "https://evolvianai.com/services/email"
    if not extra_query:
        return base
    return f"{base}?{urlencode(extra_query)}"


def _insert_channel_resilient(payload: dict):
    try:
        return supabase.table("channels").insert({**payload, "active": True}).execute()
    except Exception as e_active:
        if "active" not in str(e_active).lower():
            raise
    try:
        return supabase.table("channels").insert({**payload, "is_active": True}).execute()
    except Exception as e_is_active:
        if "is_active" not in str(e_is_active).lower():
            raise
    return supabase.table("channels").insert(payload).execute()


def _update_channel_resilient(channel_id: str, payload: dict):
    try:
        return supabase.table("channels").update({**payload, "active": True}).eq("id", channel_id).execute()
    except Exception as e_active:
        if "active" not in str(e_active).lower():
            raise
    try:
        return supabase.table("channels").update({**payload, "is_active": True}).eq("id", channel_id).execute()
    except Exception as e_is_active:
        if "is_active" not in str(e_is_active).lower():
            raise
    return supabase.table("channels").update(payload).eq("id", channel_id).execute()


def _oauth_redirect(request: Request, **query):
    return RedirectResponse(url=_ui_email_setup_url(request, query), status_code=302)


# ---------------------------------------------------------
# 1️⃣ Generar URL de autorización
#   - Guardamos 'state' vinculado al client_id (en channels como fila temporal)
# ---------------------------------------------------------
@router.get("/authorize", response_model=None)
async def authorize(request: Request, client_id: str):
    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET or not GMAIL_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Faltan variables de entorno Gmail OAuth.")
    authorize_client_request(request, client_id)

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=GMAIL_REDIRECT_URI,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes=False,
        prompt="consent",
    )

    # Guardamos el state atando client_id; usamos una fila temporal en channels
    # (reutilizamos columna gmail_access_token para almacenar el 'state')
    try:
        _insert_channel_resilient({
            "client_id": client_id,
            "type": "oauth_state",
            "provider": "gmail",
            "value": f"oauth_state:{client_id}",
            "gmail_access_token": state,  # aquí guardamos el state
            "token_uri": "https://oauth2.googleapis.com/token",  # ← nuevo
            "scope": " ".join(SCOPES),                           # ← nuevo
        })
    except Exception as e:
        print(f"⚠️ Error guardando state temporal: {e}")
        raise HTTPException(status_code=500, detail="No se pudo iniciar la conexión con Gmail")

    return {"authorization_url": authorization_url}


# ---------------------------------------------------------
# 2️⃣ Callback de Google
#   - Intercambia código → tokens
#   - Resuelve client_id a partir de 'state'
#   - Obtiene email del perfil Gmail (no usamos id_token para simplificar scopes)
#   - Upsert del canal Gmail del cliente
# ---------------------------------------------------------
@router.get("/callback", response_model=None)
async def oauth_callback(request: Request):
    t0 = time.time()
    query_params = dict(request.query_params)
    code = query_params.get("code")
    state = query_params.get("state")
    oauth_state_row_id = None

    if not code:
        return _oauth_redirect(request, gmail_error="missing_code")
    if not state:
        return _oauth_redirect(request, gmail_error="missing_state")

    try:
        print("⏱️ [1] Intercambiando código por tokens...")
        t1 = time.time()
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GMAIL_CLIENT_ID,
                    "client_secret": GMAIL_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=GMAIL_REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        print(f"✅ Tokens obtenidos en {time.time() - t1:.2f}s")

        # [2] Resuelve client_id usando 'state' guardado
        state_row = (
            supabase.table("channels")
            .select("client_id, id")
            .eq("type", "oauth_state")
            .eq("provider", "gmail")
            .eq("gmail_access_token", state)
            .maybe_single()
            .execute()
        )
        if not state_row or not getattr(state_row, "data", None) or not state_row.data.get("client_id"):
            return _oauth_redirect(request, gmail_error="state_expired")

        client_id = state_row.data["client_id"]
        oauth_state_row_id = state_row.data.get("id")

        # [3] Con los tokens, construimos el servicio y traemos el email del perfil
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        if not email:
            raise HTTPException(status_code=400, detail="No se pudo obtener el email del perfil Gmail")

        print(f"📧 Usuario Gmail: {email} | client_id: {client_id}")

        # [4] Upsert del canal Gmail del cliente (provider='gmail', type='email', value=email)
        existing_channel = (
            supabase.table("channels")
            .select("id")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", "gmail")
            .eq("value", email)
            .limit(1)
            .execute()
        )
        existing = existing_channel.data if existing_channel and hasattr(existing_channel, "data") else []

        payload_common = {
            "gmail_access_token": credentials.token,
            "gmail_refresh_token": credentials.refresh_token,
            "gmail_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            "scope": " ".join(SCOPES),
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        if existing:
            channel_id = existing[0]["id"]
            _update_channel_resilient(channel_id, payload_common)
        else:
            _insert_channel_resilient({
                "client_id": client_id,
                "type": "email",
                "provider": "gmail",
                "value": email,
                **payload_common,
            })

        print(f"✅ Canal Gmail sincronizado correctamente ({email})")

        total_time = time.time() - t0
        print(f"🏁 Flujo Gmail OAuth completado en {total_time:.2f}s")
        return _oauth_redirect(request, gmail_connected="true")

    except HTTPException as e:
        print(f"🔥 Error HTTP en flujo OAuth: {e.detail}")
        return _oauth_redirect(request, gmail_error="oauth_failed")
    except Exception as e:
        print(f"🔥 Error en flujo OAuth: {e}")
        return _oauth_redirect(request, gmail_error="oauth_failed")
    finally:
        # [5] Limpieza del state temporal (solo el usado)
        try:
            if oauth_state_row_id:
                supabase.table("channels").delete().eq("id", oauth_state_row_id).execute()
        except Exception:
            pass


# ---------------------------------------------------------
# 3️⃣ Servicio Gmail — sin file_cache + refresh con persistencia
# ---------------------------------------------------------
def get_gmail_service(channel: dict):
    """
    channel: fila de public.channels con columnas:
      - gmail_access_token, gmail_refresh_token, gmail_expiry (opcional)
      - scope (string), token_uri
      - id (channel_id), client_id, provider/type, value
    """
    scopes = (channel.get("scope") or "https://mail.google.com/").split()

    creds = Credentials(
        token=channel.get("gmail_access_token"),
        refresh_token=channel.get("gmail_refresh_token"),
        token_uri=channel.get("token_uri") or "https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        scopes=scopes,
    )

    # 🔁 Refrescar token manualmente si está vencido y persistir
    if not creds.valid or getattr(creds, "expired", False):
        try:
            creds.refresh(google_requests.Request())
            print("♻️ Token Gmail refrescado correctamente.")

            # Persistir token/expiry/scope actualizados
            try:
                supabase.table("channels").update({
                    "gmail_access_token": creds.token,
                    "gmail_expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
                    "scope": " ".join(getattr(creds, "scopes", []) or scopes),
                }).eq("id", channel.get("id")).execute()
            except Exception as e:
                print(f"⚠️ No se pudo persistir el token renovado: {e}")

        except Exception as e:
            print(f"⚠️ Error refrescando token Gmail: {e}")
            # ← nuevo: señalamos que debe reautorizar
            raise HTTPException(status_code=401, detail="Refresh token inválido o revocado. Reautorizar Gmail.")

    # Sin disco / sin discovery cache
    try:
        service = build(
            "gmail",
            "v1",
            credentials=creds,
            cache_discovery=False,
            static_discovery=False,  # algunos entornos requieren quitar este flag
        )
    except TypeError:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    print("✅ Gmail service inicializado sin cache_discovery.")
    return service


# ---------------------------------------------------------
# 4️⃣ Enviar correo Gmail (usa el canal correcto del cliente)
# ---------------------------------------------------------
@router.post("/send_reply", response_model=None)
async def send_reply(payload: dict, request: Request):
    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Falta client_id")
    to_email = str(payload.get("to_email") or "").strip().lower()
    if not to_email:
        raise HTTPException(status_code=400, detail="Falta to_email")

    purpose = str(payload.get("purpose") or "transactional").strip().lower() or "transactional"
    policy_source = str(payload.get("policy_source") or "gmail_oauth_send_reply").strip()
    source_id = (
        str(payload.get("source_id") or payload.get("thread_id") or "").strip() or None
    )
    html_body = str(payload.get("html") or "")

    if purpose == "marketing":
        campaign_id = str(payload.get("campaign_id") or "").strip()
        campaign_owner_email = str(payload.get("campaign_owner_email") or "").strip().lower()
        unsubscribe_url = str(payload.get("unsubscribe_url") or "").strip()
        company_postal_address = str(payload.get("company_postal_address") or "").strip()

        if not campaign_id:
            raise HTTPException(status_code=400, detail="campaign_id is required for marketing email")
        if not campaign_owner_email or "@" not in campaign_owner_email:
            raise HTTPException(
                status_code=400,
                detail="campaign_owner_email is required for marketing email",
            )
        if not unsubscribe_url or not unsubscribe_url.lower().startswith(("https://", "http://")):
            raise HTTPException(
                status_code=400,
                detail="unsubscribe_url (http/https) is required for marketing email",
            )
        if not company_postal_address:
            raise HTTPException(
                status_code=400,
                detail="company_postal_address is required for marketing email",
            )

        html_body = ensure_marketing_footer(
            html_body=html_body,
            unsubscribe_url=unsubscribe_url,
            campaign_owner_email=campaign_owner_email,
            company_postal_address=company_postal_address,
        )

        if not source_id:
            source_id = campaign_id

    authorize_client_request(request, client_id)

    # Filtra el canal correcto
    res = (
        supabase.table("channels")
        .select("*")
        .eq("client_id", client_id)
        .eq("type", "email")
        .eq("provider", "gmail")
        .limit(1)
        .execute()
    )
    channel = res.data[0] if res and getattr(res, "data", None) else None
    if not channel or not channel.get("gmail_access_token"):
        raise HTTPException(status_code=400, detail="Cliente no tiene Gmail conectado")

    service = get_gmail_service(channel)

    allowed, policy = begin_email_send_audit(
        client_id=client_id,
        to_email=to_email,
        purpose=purpose,
        source=policy_source,
        source_id=source_id,
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "OUTBOUND_POLICY_BLOCKED",
                "reason": policy.get("reason"),
                "proof_id": policy.get("proof_id"),
            },
        )

    msg = MIMEText(html_body, "html")
    msg["to"] = to_email
    msg["subject"] = payload.get("subject")
    msg["from"] = channel.get("value") or ""  # ← nuevo: fija el remitente del canal

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    body = {"raw": raw}
    if payload.get("thread_id"):
        body["threadId"] = payload["thread_id"]

    try:
        result = service.users().messages().send(userId="me", body=body).execute()
        complete_email_send_audit(
            client_id=client_id,
            policy_result=policy,
            success=True,
            provider_message_id=(result or {}).get("id") if isinstance(result, dict) else None,
        )
        print(f"✅ Correo enviado correctamente. ID: {result.get('id')}")
        return JSONResponse({"status": "sent", "message_id": result.get("id")})
    except Exception as e:
        complete_email_send_audit(
            client_id=client_id,
            policy_result=policy,
            success=False,
            send_error="gmail_send_exception",
        )
        print(f"🔥 Error enviando correo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 5️⃣ Smoke test (opcional) — valida perfil con el canal del cliente
# ---------------------------------------------------------
@router.get("/smoke", response_model=None)
async def smoke(request: Request, client_id: str):
    authorize_client_request(request, client_id)
    res = (
        supabase.table("channels")
        .select("*")
        .eq("client_id", client_id)
        .eq("provider", "gmail")
        .eq("type", "email")
        .limit(1)
        .execute()
    )
    channel = res.data[0] if res and getattr(res, "data", None) else None
    if not channel:
        raise HTTPException(status_code=404, detail="Canal Gmail no encontrado")

    service = get_gmail_service(channel)
    profile = service.users().getProfile(userId="me").execute()
    return {"emailAddress": profile.get("emailAddress")}
