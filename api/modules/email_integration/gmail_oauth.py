import os
import base64
import time
from email.mime.text import MIMEText
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_oauth", tags=["Gmail OAuth"])

# =====================================================
# 📧 Gmail OAuth - Evolvian AI (Optimizado + Timers)
# =====================================================

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "https://evolvianai.com/gmail_oauth/callback")
WORKSPACE_MODE = os.getenv("WORKSPACE_MODE", "false").lower() == "true"

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

if WORKSPACE_MODE:
    SCOPES += [
        "https://www.googleapis.com/auth/gmail.labels",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.addons.current.message.action",
        "https://www.googleapis.com/auth/gmail.addons.current.action.compose",
    ]


# ---------------------------------------------------------
# 1️⃣ Generar URL de autorización
# ---------------------------------------------------------
@router.get("/authorize")
async def authorize(client_id: str):
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

    try:
        supabase.table("channels").insert({
            "client_id": client_id,
            "type": "oauth_state",
            "provider": "gmail",
            "gmail_access_token": state
        }).execute()
    except Exception as e:
        print(f"⚠️ Error guardando state temporal: {e}")

    return {"authorization_url": authorization_url}


# ---------------------------------------------------------
# 2️⃣ Callback de Google (con cronómetro de etapas)
# ---------------------------------------------------------
@router.get("/callback")
async def oauth_callback(request: Request):
    t0 = time.time()
    query_params = dict(request.query_params)
    code = query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Código de autorización faltante")

    try:
        # Etapa 1️⃣: Intercambio de token
        print("⏱️ [1] Iniciando fetch_token...")
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

        flow.fetch_token(code=code, timeout=8)
        credentials = flow.credentials
        print(f"✅ [1] fetch_token completado en {time.time() - t1:.2f}s")

        # Etapa 2️⃣: Verificación de id_token
        print("⏱️ [2] Verificando id_token...")
        t2 = time.time()
        email = None
        try:
            req = google_requests.Request(timeout=3)
            info = google_id_token.verify_oauth2_token(
                credentials.id_token, req, GMAIL_CLIENT_ID
            )
            email = info.get("email")
        except Exception as e:
            print(f"⚠️ Error verificando id_token: {e}")
        print(f"✅ [2] Verificación completada en {time.time() - t2:.2f}s")

        if not email:
            raise HTTPException(status_code=400, detail="No se pudo obtener el email del usuario")

        print(f"📧 Usuario Gmail detectado: {email}")

        # Etapa 3️⃣: Buscar o crear usuario/cliente
        print("⏱️ [3] Consultando usuario/cliente en Supabase...")
        t3 = time.time()
        user_resp = (
            supabase.table("users").select("id").eq("email", email).maybe_single().execute()
        )
        if user_resp and getattr(user_resp, "data", None) and user_resp.data.get("id"):
            user_id = user_resp.data["id"]
        else:
            new_user = supabase.table("users").insert({"email": email}).execute()
            user_id = new_user.data[0]["id"]

        client_resp = (
            supabase.table("clients").select("id").eq("user_id", user_id).maybe_single().execute()
        )
        if client_resp and getattr(client_resp, "data", None) and client_resp.data.get("id"):
            client_id = client_resp.data["id"]
        else:
            inserted = supabase.table("clients").insert({
                "user_id": user_id,
                "name": email.split('@')[0]
            }).execute()
            client_id = inserted.data[0]["id"]
        print(f"✅ [3] Usuario/cliente procesado en {time.time() - t3:.2f}s")

        # Etapa 4️⃣: Guardar canal Gmail
        print("⏱️ [4] Guardando canal Gmail...")
        t4 = time.time()
        channel_query = (
            supabase.table("channels")
            .select("id")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", "gmail")
            .eq("value", email)
            .limit(1)
            .execute()
        )

        existing_channel = channel_query.data if channel_query and hasattr(channel_query, "data") else []

        if existing_channel:
            channel_id = existing_channel[0]["id"]
            supabase.table("channels").update({
                "gmail_access_token": credentials.token,
                "gmail_refresh_token": credentials.refresh_token,
                "gmail_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "active": True
            }).eq("id", channel_id).execute()
        else:
            supabase.table("channels").insert({
                "client_id": client_id,
                "type": "email",
                "provider": "gmail",
                "value": email,
                "gmail_access_token": credentials.token,
                "gmail_refresh_token": credentials.refresh_token,
                "gmail_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "active": True
            }).execute()
        print(f"✅ [4] Canal Gmail guardado en {time.time() - t4:.2f}s")

        # Etapa 5️⃣: Limpieza final + redirección
        try:
            supabase.table("channels").delete().eq("type", "oauth_state").execute()
        except Exception:
            pass

        total_time = time.time() - t0
        print(f"🏁 Flujo completo Gmail OAuth terminado en {total_time:.2f}s")

        origin = request.headers.get("origin") or ""
        redirect_url = (
            "http://localhost:4223/services/email"
            if "localhost" in origin or "127.0.0.1" in origin
            else "https://evolvianai.net/services/email"
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    except Exception as e:
        print(f"🔥 Error en flujo OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 3️⃣ Helper: servicio Gmail sin discovery
# ---------------------------------------------------------
def get_gmail_service(channel):
    creds = Credentials(
        token=channel["gmail_access_token"],
        refresh_token=channel["gmail_refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------
# 4️⃣ Enviar correo Gmail
# ---------------------------------------------------------
@router.post("/send_reply")
async def send_reply(payload: dict):
    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Falta client_id")

    res = (
        supabase.table("channels")
        .select("*")
        .eq("client_id", client_id)
        .eq("type", "email")
        .maybe_single()
        .execute()
    )

    channel = res.data
    if not channel or not channel.get("gmail_access_token"):
        raise HTTPException(status_code=400, detail="Cliente no tiene Gmail conectado")

    service = get_gmail_service(channel)

    msg = MIMEText(payload.get("html") or "", "html")
    msg["to"] = payload.get("to_email")
    msg["subject"] = payload.get("subject")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    body = {"raw": raw}
    if payload.get("thread_id"):
        body["threadId"] = payload["thread_id"]

    try:
        result = service.users().messages().send(userId="me", body=body).execute()
        print(f"✅ Correo enviado correctamente. ID: {result.get('id')}")
        return JSONResponse({"status": "sent", "message_id": result.get("id")})
    except Exception as e:
        print(f"🔥 Error enviando correo: {e}")
        raise HTTPException(status_code=500, detail=str(e))
