# api/modules/email/gmail_setup_watch.py
import os
from datetime import timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # ← nuevo: para 404/410 de history
from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests

from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/gmail_poll", tags=["Gmail Polling (sin Pub/Sub)"])

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
SCOPES = ["https://mail.google.com/"]

# ---------- Helpers OAuth/Service ----------
def _persist_refreshed_token(channel_id: str, creds: Credentials):
    try:
        supabase.table("channels").update({
            "gmail_access_token": creds.token,
            "gmail_expiry": creds.expiry.astimezone(timezone.utc).isoformat() if getattr(creds, "expiry", None) else None,
            "scope": " ".join(getattr(creds, "scopes", []) or SCOPES),
        }).eq("id", channel_id).execute()
    except Exception as e:
        print(f"⚠️ No se pudo persistir token renovado: {e}")

def _get_gmail_service_from_channel(channel: dict):
    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Faltan GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET")

    scopes = (channel.get("scope") or "https://mail.google.com/").split()
    creds = Credentials(
        token=channel.get("gmail_access_token"),
        refresh_token=channel.get("gmail_refresh_token"),
        token_uri=channel.get("token_uri") or "https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        scopes=scopes,
    )
    if not creds.valid or getattr(creds, "expired", False):
        try:
            creds.refresh(google_requests.Request())
            print("♻️ Gmail access_token refrescado.")
            _persist_refreshed_token(channel.get("id"), creds)
        except Exception as e:
            print(f"🔥 Error refrescando token Gmail: {e}")
            raise HTTPException(status_code=401, detail="No fue posible refrescar el token de Gmail")

    try:
        return build("gmail", "v1", credentials=creds, cache_discovery=False, static_discovery=False)
    except TypeError:
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

# ---------- Select canal ----------
def _select_active_gmail_channel_by_client(client_id: str) -> dict:
    resp = (
        supabase.table("channels")
        .select("*")
        .eq("client_id", client_id)
        .eq("provider", "gmail")
        .eq("type", "email")
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not resp or not getattr(resp, "data", None):
        raise HTTPException(status_code=404, detail="No se encontró canal Gmail activo para este cliente")
    ch = resp.data[0]
    if not ch.get("gmail_access_token") or not ch.get("gmail_refresh_token"):
        raise HTTPException(status_code=400, detail="El canal Gmail no tiene credenciales OAuth completas")
    return ch

# ---------- Lógica de Polling ----------
def _get_or_bootstrap_history_id(service, channel: dict) -> str:
    last = channel.get("gmail_last_history_id")
    if last:
        return str(last)
    profile = service.users().getProfile(userId="me").execute()
    base_history_id = str(profile.get("historyId"))
    supabase.table("channels").update({"gmail_last_history_id": base_history_id}).eq("id", channel["id"]).execute()
    print(f"🧭 Bootstrap historyId={base_history_id} para {channel.get('value')}")
    return base_history_id

def _list_history_changes(service, start_history_id: str) -> List[Dict[str, Any]]:
    user = "me"
    out: List[Dict[str, Any]] = []
    token: Optional[str] = None
    while True:
        resp = service.users().history().list(
            userId=user,
            startHistoryId=str(start_history_id),
            historyTypes=["messageAdded", "labelAdded", "labelRemoved"],
            pageToken=token,
            maxResults=500
        ).execute()
        out.extend(resp.get("history", []) or [])
        token = resp.get("nextPageToken")
        if not token:
            break
    return out

def _flatten_new_message_ids(changes: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    for entry in changes:
        for added in entry.get("messagesAdded", []) or []:
            msg = added.get("message", {}) or {}
            mid = msg.get("id")
            if mid:
                ids.append(mid)
    # De-dupe preservando orden
    seen, result = set(), []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            result.append(mid)
    return result

def _already_processed(message_id: str) -> bool:
    resp = supabase.table("gmail_processed").select("id").eq("message_id", message_id).maybe_single().execute()
    return bool(resp and getattr(resp, "data", None))

def _mark_processed(client_id: str, message_id: str, history_id: Optional[str]):
    try:
        supabase.table("gmail_processed").insert({
            "client_id": client_id,
            "message_id": message_id,
            "history_id": str(history_id) if history_id else None,
            "processed": True,
        }).execute()
    except Exception as e:
        print(f"ℹ️ gmail_processed duplicate? {e}")

def _fetch_and_handle_message(service, message_id: str) -> Dict[str, Any]:
    msg = service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
    headers = {h["name"].lower(): h["value"] for h in (msg.get("payload", {}) or {}).get("headers", [])}
    return {
        "id": message_id,
        "threadId": msg.get("threadId"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "snippet": msg.get("snippet"),
        "labelIds": msg.get("labelIds", []),
    }

def _update_last_history_id(channel_id: str, new_history_id: str):
    supabase.table("channels").update({"gmail_last_history_id": str(new_history_id)}).eq("id", channel_id).execute()

# ---------- Endpoints ----------
@router.post("/poll_once")
async def poll_once(client_id: str):
    try:
        ch = _select_active_gmail_channel_by_client(client_id)
        svc = _get_gmail_service_from_channel(ch)
        start_id = _get_or_bootstrap_history_id(svc, ch)

        try:
            changes = _list_history_changes(svc, start_id)
        except HttpError as he:
            # Gmail puede responder 404/410 si el startHistoryId es muy antiguo
            if he.resp.status in (404, 410):
                print(f"♻️ startHistoryId inválido para {ch.get('value')} ({start_id}); re-bootstrap…")
                # re-bootstrap usando profile actual
                profile = svc.users().getProfile(userId="me").execute()
                start_id = str(profile.get("historyId"))
                _update_last_history_id(ch["id"], start_id)
                changes = _list_history_changes(svc, start_id)
            else:
                raise

        if not changes:
            return {"status": "ok", "new_messages": 0, "note": f"sin cambios desde {start_id}"}

        latest_history_id = str(
            max(int(c.get("id")) for c in changes if c.get("id"))
        )
        new_msg_ids = _flatten_new_message_ids(changes)

        processed = []
        for mid in new_msg_ids:
            if _already_processed(mid):
                continue
            summary = _fetch_and_handle_message(svc, mid)
            # 👉 aquí conecta tu pipeline (auto-reply/etiquetado/RAG)
            _mark_processed(client_id, mid, latest_history_id)
            processed.append(summary)

        _update_last_history_id(ch["id"], latest_history_id)
        return {
            "status": "ok",
            "processed_count": len(processed),
            "latest_history_id": latest_history_id,
            "items": processed
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error en poll_once: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/poll_all")
async def poll_all():
    try:
        res = (
            supabase.table("channels")
            .select("client_id")
            .eq("provider", "gmail")
            .eq("type", "email")
            .eq("active", True)
            .execute()
        )
        rows = res.data or []
        seen, ok, errs = set(), [], []
        for r in rows:
            cid = r.get("client_id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            try:
                out = await poll_once(cid)
                ok.append({"client_id": cid, "result": out})
            except Exception as e:
                errs.append({"client_id": cid, "error": str(e)})
        return {"status": "ok", "ok": ok, "errors": errs}

    except Exception as e:
        print(f"🔥 Error en poll_all: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
