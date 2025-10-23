# api/modules/email/gmail_poll.py
import os
import time
import json
import requests
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests

from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_poll", tags=["Gmail Automation"])

# ------------------------------------------------------------
# ⚙️ Configuración global
# ------------------------------------------------------------
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")

WEBHOOK_URL = os.getenv("GMAIL_WEBHOOK_URL", "https://evolvian-assistant.onrender.com/gmail_webhook")
WEBHOOK_SECRET = os.getenv("GMAIL_WEBHOOK_SECRET", "")  # opcional para firmar

SCOPES = ["https://mail.google.com/"]  # scope único y estable

MAX_RETRIES = 3          # reintentos al enviar webhook
TIMEOUT_SECONDS = 60     # timeout por petición webhook
SLEEP_BETWEEN = 1        # pausa entre canales (suavizar carga)

# ------------------------------------------------------------
# 🔐 OAuth helpers
# ------------------------------------------------------------
def _refresh_and_persist_token(channel_id: str, creds: Credentials):
    """Refresca si expira y persiste access_token/expiry/scope."""
    if not creds.valid or getattr(creds, "expired", False):
        creds.refresh(google_requests.Request())
    try:
        supabase.table("channels").update({
            "gmail_access_token": creds.token,
            "gmail_expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
            "scope": " ".join(getattr(creds, "scopes", []) or SCOPES),
        }).eq("id", channel_id).execute()
    except Exception as e:
        print(f"⚠️ No se pudo persistir token renovado: {e}")

def _build_service(ch: dict):
    """Crea cliente Gmail con refresh + persistencia."""
    creds = Credentials(
        token=ch.get("gmail_access_token"),
        refresh_token=ch.get("gmail_refresh_token"),
        token_uri=ch.get("token_uri") or "https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        scopes=(ch.get("scope") or "https://mail.google.com/").split(),
    )
    _refresh_and_persist_token(ch["id"], creds)
    try:
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except TypeError:
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

# ------------------------------------------------------------
# 🧭 historyId helpers
# ------------------------------------------------------------
def _persist_last_history_id(channel_id: str, history_id: str):
    """Intenta guardar el último historyId; si la columna no existe, lo ignora."""
    try:
        supabase.table("channels").update({
            "gmail_last_history_id": str(history_id)
        }).eq("id", channel_id).execute()
    except Exception as e:
        # Columna podría no existir; seguimos sin fallar el proceso
        print(f"ℹ️ No se pudo persistir gmail_last_history_id: {e}")

def _get_or_bootstrap_history_id(service, channel: dict) -> str:
    """Usa el historyId guardado; si no hay, arranca desde el actual del perfil."""
    last = channel.get("gmail_last_history_id")
    if last:
        return str(last)
    profile = service.users().getProfile(userId="me").execute()
    base_history_id = str(profile.get("historyId"))
    _persist_last_history_id(channel["id"], base_history_id)
    print(f"🧭 Bootstrap historyId={base_history_id} para {channel.get('value')}")
    return base_history_id

def _list_history_changes(service, start_history_id: str) -> List[Dict[str, Any]]:
    """Lee cambios desde start_history_id con users.history.list (paginado)."""
    user = "me"
    changes: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        resp = service.users().history().list(
            userId=user,
            startHistoryId=start_history_id,
            historyTypes=["messageAdded", "labelAdded", "labelRemoved"],
            pageToken=page_token,
            maxResults=500
        ).execute()
        changes.extend(resp.get("history", []) or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return changes

def _extract_latest_history_id(changes: List[Dict[str, Any]]) -> Optional[str]:
    ids = [int(c["id"]) for c in changes if c.get("id")]
    return str(max(ids)) if ids else None

# ------------------------------------------------------------
# 📬 Webhook dispatcher
# ------------------------------------------------------------
def _send_webhook(email: str, history_id: Optional[str]):
    """Envía 1 webhook por canal con el último historyId (si hay cambios)."""
    payload = {"email": email}
    if history_id:
        payload["historyId"] = str(history_id)

    headers = {"Content-Type": "application/json"}
    if WEBHOOK_SECRET:
        headers["X-Evolvian-Signature"] = WEBHOOK_SECRET

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 200:
                print(f"✅ Webhook → {email} (historyId={history_id})")
                return True
            else:
                print(f"⚠️ Intento {attempt}/{MAX_RETRIES} → {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"⚠️ Error intento {attempt}/{MAX_RETRIES} para {email}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(2)
    return False

# ------------------------------------------------------------
# 🚀 Poll principal (para CRON)
# ------------------------------------------------------------
@router.post("/check")
async def check_new_emails():
    """
    Revisa cambios en Gmail por cliente usando historyId.
    - Un webhook por canal cuando hay nuevos cambios.
    - Resiliente a startHistoryId expirado: re-bootstrap.
    """
    print("🚀 Gmail poll (historyId) iniciando...")

    try:
        # 1) Canales Gmail activos
        channels_resp = (
            supabase.table("channels")
            .select("id, client_id, value, provider, type, active, scope, token_uri, gmail_access_token, gmail_refresh_token, gmail_last_history_id")
            .eq("type", "email")
            .eq("provider", "gmail")
            .eq("active", True)
            .execute()
        )
        channels = channels_resp.data or []
        if not channels:
            print("⚠️ No hay canales Gmail activos.")
            return {"status": "ok", "checked": [], "message": "Sin canales activos"}

        # 2) Filtra por plan (Premium/White Label)
        eligible_plans = {"premium", "white_label"}
        plan_map = {}  # cache por client_id
        processed, skipped = [], []

        for ch in channels:
            email = ch.get("value")
            client_id = ch.get("client_id")

            if client_id not in plan_map:
                cs = supabase.table("client_settings").select("plan_id").eq("client_id", client_id).maybe_single().execute()
                plan_map[client_id] = (cs.data or {}).get("plan_id", "")
            plan = (plan_map[client_id] or "").strip().lower()

            if plan not in eligible_plans:
                print(f"🟡 {email}: plan '{plan}' no elegible.")
                skipped.append(email)
                continue

            # 3) Servicio Gmail + history list
            try:
                service = _build_service(ch)

                try:
                    start_id = _get_or_bootstrap_history_id(service, ch)
                    changes = _list_history_changes(service, start_id)
                except HttpError as he:
                    # Si el startHistoryId es viejo (410/404), re-bootstrap y vuelve a intentar una sola vez
                    if he.resp.status in (404, 410):
                        print(f"♻️ startHistoryId inválido para {email}, re-bootstrap…")
                        start_id = _get_or_bootstrap_history_id(service, {"id": ch["id"], "value": email})
                        changes = _list_history_changes(service, start_id)
                    else:
                        raise

                if not changes:
                    print(f"🟢 {email}: sin cambios desde historyId={start_id}.")
                    processed.append(email)
                    time.sleep(SLEEP_BETWEEN)
                    continue

                latest_history_id = _extract_latest_history_id(changes)
                if latest_history_id:
                    _persist_last_history_id(ch["id"], latest_history_id)

                # 4) Dispara 1 webhook por canal con el último historyId
                _send_webhook(email, latest_history_id)
                processed.append(email)
                time.sleep(SLEEP_BETWEEN)

            except Exception as e:
                print(f"🔥 Error procesando {email}: {e}")

        return JSONResponse({"status": "ok", "processed": processed, "skipped": skipped})

    except Exception as e:
        print(f"💥 Error global gmail_poll/check: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
