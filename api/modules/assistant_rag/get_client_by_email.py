from fastapi import APIRouter, HTTPException, Query
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(
    prefix="/get_client_by_email",
    tags=["Email Automation"]
)

@router.get("")
async def get_client_by_email(email: str = Query(..., description="Email registrado en el canal del cliente")):
    """
    Retorna el client_id y metadatos asociados a un email registrado como canal.
    Este endpoint es usado por n8n y los flujos de automatización.
    """
    print(f"📧 Buscando cliente asociado al email: {email}")

    if not email:
        raise HTTPException(status_code=400, detail="Se requiere un parámetro 'email'")

    # 🔹 Buscar canal activo asociado al email
    try:
        channel_resp = (
            supabase.table("channels")
            .select("client_id, value, type, provider, active")
            .eq("value", email)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        if not channel_resp.data or len(channel_resp.data) == 0:
            print("⚠️ Ningún canal activo encontrado para este email.")
            raise HTTPException(status_code=404, detail="Email no asociado a ningún cliente activo")

        channel = channel_resp.data[0]
        client_id = channel["client_id"]
        print(f"🔗 Canal encontrado. client_id={client_id}")

    except Exception as e:
        print(f"🔥 Error consultando canales: {e}")
        raise HTTPException(status_code=500, detail="Error interno buscando el canal de email")

    # 🔹 Obtener info adicional del cliente
    try:
        client_resp = (
            supabase.table("clients")
            .select("id, name, public_client_id")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )

        if not client_resp.data or len(client_resp.data) == 0:
            print("⚠️ Cliente no encontrado en la tabla clients.")
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        client = client_resp.data[0]
        print(f"✅ Cliente encontrado: {client['name']}")

        return {
            "client_id": client["id"],
            "public_client_id": client["public_client_id"],
            "client_name": client["name"],
            "email_channel": channel["value"],
            "type": channel["type"],
            "provider": channel["provider"]
        }

    except Exception as e:
        print(f"🔥 Error obteniendo datos del cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno consultando cliente")
