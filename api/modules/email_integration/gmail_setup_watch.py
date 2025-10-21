import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_watch", tags=["Gmail Watch Setup"])

# ---------------------------------------------------------
# 🌐 Variables de entorno
# ---------------------------------------------------------
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
WEBHOOK_URL = os.getenv("GMAIL_WEBHOOK_URL", "https://evolvian-assistant.onrender.com/gmail_webhook")
TOPIC_NAME = os.getenv("GMAIL_PUBSUB_TOPIC", "projects/evolvian-ai/topics/gmail-notifications")

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ---------------------------------------------------------
# 🧠 Helper: crear servicio Gmail desde canal Supabase
# ---------------------------------------------------------
def get_gmail_service_from_channel(channel):
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
# 🚀 1️⃣ Endpoint manual para iniciar Watch
# ---------------------------------------------------------
@router.post("/start")
async def start_gmail_watch(client_id: str):
    """
    Activa el Gmail Watch para un cliente.
    Requiere:
      - client_id existente
      - Canal de tipo 'email' con credenciales OAuth
    """
    try:
        print(f"📡 Iniciando Gmail Watch para client_id={client_id}")

        # 🔍 Buscar canal Gmail activo
        channel_resp = (
            supabase.table("channels")
            .select("*")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("active", True)
            .limit(1)
            .execute()
        )

        if not channel_resp.data or not channel_resp.data[0].get("gmail_access_token"):
            raise HTTPException(status_code=404, detail="No se encontró canal Gmail válido para este cliente")

        channel = channel_resp.data[0]
        service = get_gmail_service_from_channel(channel)

        # ⚙️ Configurar watch request
        watch_request = {
            "labelIds": ["INBOX"],
            "topicName": TOPIC_NAME,  # Nombre del tópico Pub/Sub configurado
        }

        response = service.users().watch(userId="me", body=watch_request).execute()
        print(f"✅ Watch creado correctamente para {channel['value']}")
        print(f"🔔 Expira el {datetime.utcnow() + timedelta(hours=6)} UTC")

        # Guardar info en Supabase (opcional)
        supabase.table("channels").update({
            "gmail_watch_expiry": (datetime.utcnow() + timedelta(hours=6)).isoformat(),
            "gmail_history_id": response.get("historyId"),
        }).eq("id", channel["id"]).execute()

        return JSONResponse({
            "status": "ok",
            "email": channel["value"],
            "watch_expiry": datetime.utcnow() + timedelta(hours=6),
            "history_id": response.get("historyId"),
        })

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"🔥 Error iniciando Gmail Watch: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ---------------------------------------------------------
# 🔁 2️⃣ Endpoint opcional: detener Watch
# ---------------------------------------------------------
@router.post("/stop")
async def stop_gmail_watch(client_id: str):
    """
    Detiene el watch de Gmail para un cliente.
    """
    try:
        channel_resp = (
            supabase.table("channels")
            .select("*")
            .eq("client_id", client_id)
            .eq("type", "email")
            .limit(1)
            .execute()
        )

        if not channel_resp.data or not channel_resp.data[0].get("gmail_access_token"):
            raise HTTPException(status_code=404, detail="No se encontró canal Gmail válido")

        channel = channel_resp.data[0]
        service = get_gmail_service_from_channel(channel)
        service.users().stop(userId="me").execute()

        supabase.table("channels").update({
            "gmail_watch_expiry": None,
            "gmail_history_id": None
        }).eq("id", channel["id"]).execute()

        print(f"🛑 Gmail Watch detenido para {channel['value']}")
        return {"status": "stopped", "email": channel["value"]}

    except Exception as e:
        print(f"🔥 Error deteniendo Gmail Watch: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ---------------------------------------------------------
# 🔄 3️⃣ Endpoint opcional: renovar automáticamente el Watch
# ---------------------------------------------------------
@router.post("/refresh_all")
async def refresh_all_watches():
    """
    Renueva el Watch de todos los clientes activos con Gmail.
    Útil para CRON jobs (cada 6h en Render).
    """
    try:
        channels = (
            supabase.table("channels")
            .select("*")
            .eq("type", "email")
            .eq("active", True)
            .execute()
        ).data

        refreshed = []
        for ch in channels:
            try:
                service = get_gmail_service_from_channel(ch)
                watch_request = {"labelIds": ["INBOX"], "topicName": TOPIC_NAME}
                service.users().watch(userId="me", body=watch_request).execute()

                supabase.table("channels").update({
                    "gmail_watch_expiry": (datetime.utcnow() + timedelta(hours=6)).isoformat(),
                }).eq("id", ch["id"]).execute()

                refreshed.append(ch["value"])
                print(f"🔁 Watch renovado: {ch['value']}")
            except Exception as inner_e:
                print(f"⚠️ Error renovando watch para {ch['value']}: {inner_e}")

        return {"status": "ok", "refreshed": refreshed}

    except Exception as e:
        print(f"🔥 Error en refresh_all_watches: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
