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
# 📬 Poll manual de correos Gmail (clientes Premium y White Label)
# ------------------------------------------------------------
@router.post("/check")
async def check_new_emails():
    """
    🔍 Verifica correos nuevos en las cuentas Gmail conectadas
    para clientes activos con plan Premium o White Label.
    Ideal para ejecutarse como CRON cada 5 minutos.
    """

    print("🚀 Iniciando revisión de correos Gmail para clientes Premium y White Label...")

    try:
        # 1️⃣ Buscar canales Gmail activos
        channels_resp = (
            supabase.table("channels")
            .select("client_id, value, gmail_access_token, gmail_refresh_token, active")
            .eq("type", "email")
            .eq("active", True)
            .execute()
        )

        if not channels_resp.data:
            print("⚠️ No hay canales Gmail activos en la tabla channels.")
            return {"status": "ok", "checked": [], "message": "Sin canales activos"}

        channels = channels_resp.data
        print(f"📊 {len(channels)} canales Gmail activos encontrados.")

        processed = []
        eligible_plans = ["premium", "white_label"]

        # 2️⃣ Filtrar por plan_id
        for ch in channels:
            client_id = ch.get("client_id")
            email = ch.get("value")

            settings_resp = (
                supabase.table("client_settings")
                .select("plan_id")
                .eq("client_id", client_id)
                .execute()
            )

            if not settings_resp.data:
                print(f"⚠️ {email}: sin configuración de cliente.")
                continue

            plan_id = settings_resp.data[0].get("plan_id", "").strip().lower()

            if plan_id not in eligible_plans:
                print(f"🟡 {email}: plan '{plan_id}', no es premium ni white_label.")
                continue

            # 3️⃣ Revisar correos
            try:
                creds = Credentials(
                    token=ch["gmail_access_token"],
                    refresh_token=ch["gmail_refresh_token"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=GMAIL_CLIENT_ID,
                    client_secret=GMAIL_CLIENT_SECRET,
                    scopes=SCOPES,
                )

                service = build("gmail", "v1", credentials=creds)
                results = (
                    service.users()
                    .messages()
                    .list(userId="me", labelIds=["INBOX"], maxResults=3)
                    .execute()
                )

                messages = results.get("messages", [])
                if messages:
                    print(f"📩 {email}: {len(messages)} mensajes recientes.")
                    for msg in messages:
                        print(f"   ➤ ID: {msg['id']}")
                    processed.append(email)
                else:
                    print(f"🟢 {email}: sin mensajes nuevos.")
            except Exception as e:
                print(f"⚠️ Error verificando {email}: {e}")

        if not processed:
            print("✅ No se encontraron correos nuevos en clientes premium o white_label.")
        else:
            print(f"✅ Procesados: {processed}")

        return JSONResponse({"status": "ok", "checked": processed})

    except Exception as e:
        print(f"🔥 Error global en gmail_poll/check: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
