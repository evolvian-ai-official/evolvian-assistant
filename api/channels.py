# api/channels.py
from fastapi import APIRouter, HTTPException, Query, Request
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(prefix="/channels", tags=["Email Automation"])
SAFE_CHANNEL_COLUMNS = (
    "id, client_id, type, provider, value, active, is_active, "
    "wa_phone_id, created_at, updated_at, archived_at, archived_reason, "
    "last_connected_at, last_disconnected_at"
)

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
        query = supabase.table("channels").select(SAFE_CHANNEL_COLUMNS).eq("client_id", client_id)
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
                .select(SAFE_CHANNEL_COLUMNS)
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

        print(f"📦 Canales encontrados: {len(data)}")
        for d in data:
            print(f" → Canal: {d.get('provider')} ({d.get('value')}) activo={d.get('active')}")

        if not data:
            raise HTTPException(status_code=404, detail="No se encontraron canales")

        return data

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error consultando canales: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno al consultar canales: {e}")
