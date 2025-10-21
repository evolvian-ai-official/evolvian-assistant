import os
import base64
from email.mime.text import MIMEText
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase

# =====================================================
# 📧 Gmail OAuth - Evolvian AI (Protección anti-duplicados + manejo seguro)
# =====================================================

router = APIRouter(prefix="/gmail_oauth", tags=["Gmail OAuth"])

# ---------------------------------------------------------
# 🔐 CONFIG
# ---------------------------------------------------------
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
    """
    Devuelve la URL de autorización para que el cliente conecte su Gmail.
    """
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
        include_granted_scopes="true",
        prompt="consent"
    )

    # Guardamos temporalmente el state
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
# 2️⃣ Callback de Google
# ---------------------------------------------------------
@router.get("/callback")
async def oauth_callback(request: Request):
    """
    Recibe el código de Google y guarda los tokens en Supabase.
    Previene duplicados, limpia oauth_state y actualiza canales existentes.
    """
    query_params = dict(request.query_params)
    code = query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Código de autorización faltante")

    try:
        # Intercambiar code por tokens
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

        # Obtener email
        email = None
        if credentials.id_token:
            try:
                info = google_id_token.verify_oauth2_token(
                    credentials.id_token,
                    google_requests.Request(),
                    GMAIL_CLIENT_ID
                )
                email = info.get("email")
            except Exception as e:
                print(f"⚠️ No se pudo decodificar id_token: {e}")

        if not email:
            raise HTTPException(status_code=400, detail="No se pudo obtener el email del usuario")

        print(f"✅ Gmail OAuth completado para {email}")

        # -------------------------------------------------
        # 3️⃣ Buscar o crear user y client correctamente
        # -------------------------------------------------
        client_id = None
        user_id = None

        user_resp = (
            supabase.table("users")
            .select("id")
            .eq("email", email)
            .maybe_single()
            .execute()
        )

        if user_resp and getattr(user_resp, "data", None) and user_resp.data.get("id"):
            user_id = user_resp.data["id"]
            print(f"✅ Usuario encontrado: {user_id}")
        else:
            print("🆕 Usuario no encontrado, creando nuevo...")
            new_user = supabase.table("users").insert({"email": email}).execute()
            user_id = new_user.data[0]["id"]
            print(f"✅ Usuario creado: {user_id}")

        client_resp = (
            supabase.table("clients")
            .select("id, user_id")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        if client_resp and getattr(client_resp, "data", None) and client_resp.data.get("id"):
            client_id = client_resp.data["id"]
            print(f"✅ Cliente asociado encontrado: {client_id}")
        else:
            inserted = supabase.table("clients").insert({
                "user_id": user_id,
                "name": email.split('@')[0]
            }).execute()
            client_id = inserted.data[0]["id"]
            print(f"✅ Cliente creado: {client_id}")

        # -------------------------------------------------
        # 4️⃣ Guardar canal Gmail con client_id correcto (sin duplicar)
        # -------------------------------------------------
        try:
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
        except Exception as e:
            print(f"⚠️ Error consultando canal Gmail existente: {e}")
            existing_channel = []

        if existing_channel and len(existing_channel) > 0:
            channel_id = existing_channel[0]["id"]
            print(f"🔁 Canal existente detectado ({email}), actualizando tokens...")

            supabase.table("channels").update({
                "gmail_access_token": credentials.token,
                "gmail_refresh_token": credentials.refresh_token,
                "gmail_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "active": True
            }).eq("id", channel_id).execute()

            print(f"✅ Canal Gmail actualizado correctamente para {email}")

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
            print(f"✅ Canal Gmail insertado correctamente para {email} → client_id {client_id}")

        # -------------------------------------------------
        # 5️⃣ Limpiar estados OAuth huérfanos
        # -------------------------------------------------
        try:
            supabase.table("channels").delete().eq("type", "oauth_state").execute()
            print("🧹 Limpieza: estados OAuth antiguos eliminados.")
        except Exception as e:
            print(f"⚠️ Error limpiando oauth_state: {e}")

        # Detectar entorno actual (local o producción)
        origin = request.headers.get("origin") or ""
        if "localhost" in origin or "127.0.0.1" in origin:
            redirect_url = "http://localhost:4223/services/email"
        else:
            redirect_url = "https://evolvianai.net/services/email"

        print(f"🔁 Reedirecting to Evolvian: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=302)


    except Exception as e:
        print(f"🔥 Error procesando callback OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 3️⃣ Helper: crear servicio Gmail
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
    return build("gmail", "v1", credentials=creds)

# ---------------------------------------------------------
# 4️⃣ Endpoint: enviar correo con Gmail conectado
# ---------------------------------------------------------
@router.post("/send_reply")
async def send_reply(payload: dict):
    """
    Envía un correo (nuevo o respuesta) usando las credenciales Gmail del cliente.
    payload:
      - client_id
      - to_email
      - subject
      - html (contenido)
      - thread_id (opcional)
    """
    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Falta client_id")

    res = supabase.table("channels").select("*").eq("client_id", client_id).eq("type", "email").maybe_single().execute()
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
