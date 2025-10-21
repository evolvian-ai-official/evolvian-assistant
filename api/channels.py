# api/channels.py
from fastapi import APIRouter, HTTPException, Query
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/channels", tags=["Email Automation"])

@router.get("")
async def get_channels(
    client_id: str = Query(..., description="Client ID del cliente"),
    type: str = Query(None, description="Tipo de canal (email, whatsapp, etc.)"),
    provider: str = Query(None, description="Proveedor del canal (gmail, twilio, etc.)")
):
    """
    Devuelve los canales registrados para un cliente.
    Ejemplo:
    GET /channels?client_id=123&type=email&provider=gmail
    """
    print(f"🔍 Buscando canales de client_id={client_id}, type={type}, provider={provider}")

    try:
        query = supabase.table("channels").select("*").eq("client_id", client_id)

        if type:
            query = query.ilike("type", type)
        if provider:
            query = query.ilike("provider", provider)

        result = query.execute()
        data = result.data or []

        print(f"📦 Canales encontrados: {len(data)}")
        return data

    except Exception as e:
        print(f"🔥 Error consultando canales: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar canales")
