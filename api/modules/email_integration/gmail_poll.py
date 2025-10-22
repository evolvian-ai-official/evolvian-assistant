import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_poll", tags=["Gmail Automation"])

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# ------------------------------------------------------------
# 📬 Poll manual de correos Gmail (solo clientes Premium activos)
# ------------------------------------------------------------
@router.post("/check")
async def check_new_emails():
    """
    🔍 Verifica correos nuevos en las cuentas Gmail conectadas
    para clientes activos con plan Premium.
    Ideal para ejecutarse como CRON cada 5 minutos.
    """

    print("🚀 Iniciando revisión de correos Gmail para clientes Premium...")

    try:
        # 1️⃣ Buscar canales Gmail activos con plan Premium
        query = """
        SELECT c.*, cs.plan_id, p.name AS plan_name
        FROM channels c
        JOIN client_settings cs ON cs.client_id = c.client_id
        JOIN plans p ON p.id = cs.plan_id
        WHERE c.active = true
        AND c.type = 'email'
        AND LOWER(p.name) = 'premium'
        """
        response = supabase.rpc("exec_sql", {"query": query}).execute()
        channels = response.data if response.data else []

        if not channels:
            print("⚠️ No hay clientes Premium con Gmail conectado.")
            return {"status": "ok", "checked": [], "message": "Sin clientes premium activos"}

        processed = []
        for ch in channels:
            try:
                email = ch.get("value")
                client_id = ch.get("client_id")

                creds = Credentials(
                    token=ch["gmail_access_token"],
                    refresh_token=ch["gmail_refresh_token"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=GMAIL_CLIENT_ID,
                    client_secret=GMAIL_CLIENT_SECRET,
                    scopes=SCOPES,
                )

                service = build("gmail", "v1", credentials=creds)

                # 2️⃣ Obtener últimos correos
                results = (
                    service.users()
                    .messages()
                    .list(userId="me", labelIds=["INBOX"], maxResults=3)
                    .execute()
                )

                messages = results.get("messages", [])
                if messages:
                    print(f"📩 {email} tiene {len(messages)} mensajes recientes.")
                    for msg in messages:
                        print(f"   ➤ ID: {msg['id']}")
                    processed.append(email)
                else:
                    print(f"🟢 {email}: sin mensajes nuevos.")

            except Exception as e:
                print(f"⚠️ Error procesando {ch.get('value')}: {e}")

        return JSONResponse({"status": "ok", "checked": processed})

    except Exception as e:
        print(f"🔥 Error global en gmail_poll/check: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
