import os
import time
import json
import base64
import requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_poll", tags=["Gmail Automation"])

# ------------------------------------------------------------
# ⚙️ Configuración global
# ------------------------------------------------------------
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
WEBHOOK_URL = "https://evolvian-assistant.onrender.com/gmail_webhook"

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
]

MAX_RETRIES = 3          # Número de reintentos al enviar webhook
TIMEOUT_SECONDS = 60     # Timeout por petición webhook
SLEEP_BETWEEN = 2        # Pausa entre webhooks (segundos)


# ------------------------------------------------------------
# 📬 Poll manual de correos Gmail (Premium y White Label)
# ------------------------------------------------------------
@router.post("/check")
async def check_new_emails():
    """
    🔍 Revisa nuevos correos Gmail para clientes con plan Premium o White Label.
    - Se ejecuta como CRON cada pocos minutos.
    - Emula notificaciones Pub/Sub enviando payloads al webhook.
    - Incluye reintentos y timeouts seguros.
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
            print("⚠️ No hay canales Gmail activos.")
            return {"status": "ok", "checked": [], "message": "Sin canales activos"}

        channels = channels_resp.data
        print(f"📊 {len(channels)} canales Gmail activos encontrados.")
        processed = []

        eligible_plans = ["premium", "white_label"]

        # 2️⃣ Procesar cada canal Gmail activo
        for ch in channels:
            client_id = ch.get("client_id")
            email = ch.get("value")

            # Verificar plan del cliente
            settings_resp = (
                supabase.table("client_settings")
                .select("plan_id")
                .eq("client_id", client_id)
                .execute()
            )

            if not settings_resp.data:
                print(f"⚠️ {email}: sin configuración en client_settings.")
                continue

            plan_id = settings_resp.data[0].get("plan_id", "").strip().lower()
            if plan_id not in eligible_plans:
                print(f"🟡 {email}: plan '{plan_id}' no es Premium ni White Label.")
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
                if not messages:
                    print(f"🟢 {email}: sin mensajes nuevos.")
                    continue

                print(f"📩 {email}: {len(messages)} mensajes detectados.")

                for msg in messages:
                    msg_id = msg["id"]
                    print(f"   ➤ ID: {msg_id}")

                    # Payload emulando Pub/Sub
                    payload = {
                        "message": {
                            "data": base64.b64encode(
                                json.dumps({
                                    "emailAddress": email,
                                    "historyId": str(msg_id)
                                }).encode("utf-8")
                            ).decode("utf-8")
                        }
                    }

                    # 4️⃣ Enviar webhook con reintentos
                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            resp = requests.post(
                                WEBHOOK_URL,
                                json=payload,
                                headers={"Content-Type": "application/json"},
                                timeout=TIMEOUT_SECONDS,
                            )

                            if resp.status_code == 200:
                                print(f"✅ Webhook enviado correctamente → {email} ({resp.status_code})")
                                break
                            else:
                                print(f"⚠️ Intento {attempt}/{MAX_RETRIES} → respuesta {resp.status_code}")
                        except Exception as e:
                            print(f"⚠️ Error intento {attempt}/{MAX_RETRIES} para {email}: {e}")

                        if attempt < MAX_RETRIES:
                            time.sleep(3)

                    time.sleep(SLEEP_BETWEEN)

                processed.append(email)

            except Exception as e:
                print(f"🔥 Error verificando correos para {email}: {e}")

        # Resumen final
        if processed:
            print(f"✅ Procesados correctamente: {processed}")
        else:
            print("✅ Sin correos nuevos en clientes Premium o White Label.")

        return JSONResponse({"status": "ok", "checked": processed})

    except Exception as e:
        print(f"💥 Error global en gmail_poll/check: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
