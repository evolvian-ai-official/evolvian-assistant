# api/channels.py
from datetime import datetime, timezone
import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
from api.security.whatsapp_token_crypto import (
    encrypt_whatsapp_token,
    is_encrypted_whatsapp_token,
)

router = APIRouter(prefix="/channels", tags=["Email Automation"])
logger = logging.getLogger(__name__)
SAFE_CHANNEL_FIELDS = {
    "id",
    "client_id",
    "type",
    "provider",
    "value",
    "active",
    "is_active",
    "wa_phone_id",
    "created_at",
    "updated_at",
    "archived_at",
    "archived_reason",
    "last_connected_at",
    "last_disconnected_at",
}


class EmailSenderStatusPayload(BaseModel):
    client_id: str
    enabled: bool
    provider: str = "gmail"


class MetaAppChannelUpsertPayload(BaseModel):
    client_id: str
    channel_type: Literal["messenger", "instagram"]
    recipient_id: str
    access_token: str | None = None
    provider: str = "meta"


class MetaAppChannelDisconnectPayload(BaseModel):
    client_id: str
    channel_type: Literal["messenger", "instagram"]
    provider: str = "meta"


def _sanitize_channels(rows):
    clean_rows = []
    for row in rows or []:
        if isinstance(row, dict):
            clean_rows.append({k: v for k, v in row.items() if k in SAFE_CHANNEL_FIELDS})
    return clean_rows


_RECIPIENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{5,100}$")


def _validate_meta_recipient_id(value: str) -> str:
    candidate = str(value or "").strip()
    if not _RECIPIENT_ID_RE.match(candidate):
        raise HTTPException(
            status_code=422,
            detail="recipient_id must be 5-100 chars [A-Za-z0-9_.:-]",
        )
    return candidate


def _normalize_provider(value: str | None) -> str:
    return str(value or "meta").strip().lower() or "meta"


def _encrypt_or_passthrough_token(raw: str) -> str:
    token = str(raw or "").strip()
    if not token:
        return ""
    if is_encrypted_whatsapp_token(token):
        return token
    try:
        return encrypt_whatsapp_token(token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"token_encryption_failed: {e}")


@router.get("")
async def get_channels(
    request: Request,
    client_id: str = Query(..., description="Client ID del cliente"),
    type: str = Query(None, description="Tipo de canal (email, whatsapp, etc.)"),
    provider: str = Query(None, description="Proveedor del canal (gmail, twilio, etc.)")
):
    logger.info("🔍 Buscando canales | client_id=%s | type=%s | provider=%s", client_id, type, provider)

    try:
        authorize_client_request(request, client_id)
        query = supabase.table("channels").select("*").eq("client_id", client_id)
        if type:
            query = query.eq("type", type.strip().lower())
        if provider:
            query = query.eq("provider", provider.strip().lower())

        result = query.execute()
        if getattr(result, "error", None):
            logger.warning("⚠️ Error en consulta Supabase channels: %s", result.error)

        data = getattr(result, "data", None)
        if not data:
            logger.info("🚫 Sin resultados exactos. Probando búsqueda laxa en channels")

            # Fallback de búsqueda laxa (por si hay espacios o mayúsculas)
            fallback_query = (
                supabase.table("channels")
                .select("*")
                .eq("client_id", client_id)
            )
            if provider:
                fallback_query = fallback_query.ilike("provider", f"%{provider}%")
            if type:
                fallback_query = fallback_query.ilike("type", f"%{type}%")

            result_fallback = fallback_query.execute()
            data = result_fallback.data or []

        if isinstance(data, dict):
            data = [data]
        data = _sanitize_channels(data)

        logger.info("📦 Canales encontrados: %s", len(data))
        for d in data:
            logger.info(
                " → Canal: "
                f"{d.get('provider')} ({d.get('value')}) "
                f"activo={d.get('active', d.get('is_active'))}"
            )

        if not data:
            raise HTTPException(status_code=404, detail="No se encontraron canales")

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("🔥 Error consultando canales")
        raise HTTPException(status_code=500, detail=f"Error interno al consultar canales: {e}")


@router.post("/email_sender_status")
async def set_email_sender_status(payload: EmailSenderStatusPayload, request: Request):
    """
    Activa/desactiva el uso del canal Gmail del cliente para envíos salientes.
    No elimina credenciales; solo cambia estado del canal.
    """
    client_id = payload.client_id
    provider = (payload.provider or "gmail").strip().lower()
    enabled = bool(payload.enabled)

    try:
        authorize_client_request(request, client_id)

        res = (
            supabase
            .table("channels")
            .select("*")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", provider)
            .execute()
        )
        channels = res.data or []
        if not channels:
            raise HTTPException(status_code=404, detail="No Gmail channel found for this client")

        now_iso = datetime.now(timezone.utc).isoformat()
        updated = 0

        for ch in channels:
            update_data = {"updated_at": now_iso}

            if "active" in ch:
                update_data["active"] = enabled
            if "is_active" in ch:
                update_data["is_active"] = enabled

            if enabled:
                update_data["last_connected_at"] = now_iso
            else:
                update_data["last_disconnected_at"] = now_iso

            if "active" not in update_data and "is_active" not in update_data:
                # fallback para esquemas legacy donde no vino metadata completa
                update_data["active"] = enabled

            try:
                (
                    supabase
                    .table("channels")
                    .update(update_data)
                    .eq("id", ch["id"])
                    .execute()
                )
            except Exception:
                # fallback minimal para esquemas que no tengan campos de auditoría
                minimal_update = {}
                if "active" in ch:
                    minimal_update["active"] = enabled
                if "is_active" in ch:
                    minimal_update["is_active"] = enabled
                if not minimal_update:
                    minimal_update["active"] = enabled
                (
                    supabase
                    .table("channels")
                    .update(minimal_update)
                    .eq("id", ch["id"])
                    .execute()
                )
            updated += 1

        return {
            "success": True,
            "enabled": enabled,
            "updated_channels": updated,
            "provider": provider,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error actualizando email sender status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed updating email sender status: {e}")


@router.post("/meta_app_channel")
async def upsert_meta_app_channel(payload: MetaAppChannelUpsertPayload, request: Request):
    """
    Upsert Messenger/Instagram channel credentials using existing `channels` schema.
    - `type` = messenger | instagram
    - `value` = recipient/page/business id
    - `wa_token` = encrypted access token (reused secure column)
    """
    client_id = payload.client_id
    channel_type = payload.channel_type
    provider = _normalize_provider(payload.provider)
    recipient_id = _validate_meta_recipient_id(payload.recipient_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        authorize_client_request(request, client_id)
        if provider != "meta":
            raise HTTPException(status_code=400, detail="provider must be meta")

        existing_res = (
            supabase.table("channels")
            .select("*")
            .eq("client_id", client_id)
            .eq("type", channel_type)
            .eq("provider", provider)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        existing = (existing_res.data or [None])[0]

        incoming_token = str(payload.access_token or "").strip()
        token_to_store = _encrypt_or_passthrough_token(incoming_token) if incoming_token else ""
        if not token_to_store and existing and str(existing.get("wa_token") or "").strip():
            token_to_store = str(existing.get("wa_token") or "").strip()
        if not token_to_store:
            raise HTTPException(status_code=422, detail="access_token is required for first connection")

        base_update = {
            "value": recipient_id,
            "wa_token": token_to_store,
            "provider": provider,
            "is_active": True,
            "active": True,
            "updated_at": now_iso,
            "archived_at": None,
            "archived_reason": None,
            "last_connected_at": now_iso,
            "last_disconnected_at": None,
        }

        row_id = None
        if existing and existing.get("id"):
            row_id = str(existing["id"])
            (
                supabase.table("channels")
                .update(base_update)
                .eq("id", row_id)
                .eq("client_id", client_id)
                .execute()
            )
        else:
            row_id = str(uuid.uuid4())
            insert_payload = {
                "id": row_id,
                "client_id": client_id,
                "type": channel_type,
                **base_update,
                "created_at": now_iso,
            }
            supabase.table("channels").insert(insert_payload).execute()

        return {
            "success": True,
            "client_id": client_id,
            "channel_type": channel_type,
            "provider": provider,
            "connected": True,
            "recipient_id": recipient_id,
            "channel_id": row_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"meta_app_channel_upsert_failed: {e}")


@router.post("/meta_app_channel/disconnect")
async def disconnect_meta_app_channel(payload: MetaAppChannelDisconnectPayload, request: Request):
    client_id = payload.client_id
    channel_type = payload.channel_type
    provider = _normalize_provider(payload.provider)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        authorize_client_request(request, client_id)
        if provider != "meta":
            raise HTTPException(status_code=400, detail="provider must be meta")

        (
            supabase.table("channels")
            .update(
                {
                    "is_active": False,
                    "active": False,
                    "updated_at": now_iso,
                    "archived_at": now_iso,
                    "archived_reason": "manual_disconnect",
                    "last_disconnected_at": now_iso,
                }
            )
            .eq("client_id", client_id)
            .eq("type", channel_type)
            .eq("provider", provider)
            .execute()
        )

        return {
            "success": True,
            "client_id": client_id,
            "channel_type": channel_type,
            "provider": provider,
            "connected": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"meta_app_channel_disconnect_failed: {e}")
