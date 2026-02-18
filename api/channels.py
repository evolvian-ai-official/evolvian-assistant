# api/channels.py
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(prefix="/channels", tags=["Email Automation"])
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


def _sanitize_channels(rows):
    clean_rows = []
    for row in rows or []:
        if isinstance(row, dict):
            clean_rows.append({k: v for k, v in row.items() if k in SAFE_CHANNEL_FIELDS})
    return clean_rows


@router.get("")
async def get_channels(
    request: Request,
    client_id: str = Query(..., description="Client ID del cliente"),
    type: str = Query(None, description="Tipo de canal (email, whatsapp, etc.)"),
    provider: str = Query(None, description="Proveedor del canal (gmail, twilio, etc.)")
):
    print(f"🔍 Buscando canales de client_id={client_id}, type={type}, provider={provider}")

    try:
        authorize_client_request(request, client_id)
        query = supabase.table("channels").select("*").eq("client_id", client_id)
        if type:
            query = query.eq("type", type.strip().lower())
        if provider:
            query = query.eq("provider", provider.strip().lower())

        result = query.execute()
        print("🧾 Resultado bruto de Supabase:", result)
        if getattr(result, "error", None):
            print("⚠️ Error en consulta Supabase:", result.error)

        data = getattr(result, "data", None)
        if not data:
            print("🚫 Sin resultados para ese filtro exacto. Probando búsqueda laxa...")

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
            print("🧾 Resultado fallback:", result_fallback)
            data = result_fallback.data or []

        if isinstance(data, dict):
            data = [data]
        data = _sanitize_channels(data)

        print(f"📦 Canales encontrados: {len(data)}")
        for d in data:
            print(
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
        print(f"🔥 Error consultando canales: {e}")
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
