from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
import uuid

router = APIRouter()

class WhatsAppLinkPayload(BaseModel):
    auth_user_id: str
    email: str
    phone: str  # sin whatsapp: al inicio
    provider: str = "meta"
    wa_phone_id: str | None = None
    wa_token: str | None = None

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload):
    try:
        # 1. Buscar usuario
        user_res = supabase.table("users")\
            .select("id")\
            .eq("id", payload.auth_user_id)\
            .single()\
            .execute()

        if not user_res.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_id = user_res.data["id"]

        # 2. Buscar cliente asociado
        client_res = supabase.table("clients")\
            .select("id")\
            .eq("user_id", user_id)\
            .single()\
            .execute()

        if not client_res.data:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        client_id = client_res.data["id"]

        # 3. Formatear número
        full_value = f"whatsapp:+{payload.phone.lstrip('+')}"

        # 4. Datos del canal a guardar o actualizar
        data = {
            "client_id": client_id,
            "type": "whatsapp",
            "value": full_value,
            "provider": payload.provider,
            "wa_phone_id": payload.wa_phone_id,
            "wa_token": payload.wa_token,
        }

        # 5. Buscar si ya existe canal
        existing = supabase.table("channels")\
            .select("id")\
            .eq("type", "whatsapp")\
            .eq("value", full_value)\
            .maybe_single()\
            .execute()

        if existing.data:
            # Si ya existe, actualizar
            supabase.table("channels")\
                .update(data)\
                .eq("id", existing.data["id"])\
                .execute()
        else:
            # Si no existe, insertar
            data["id"] = str(uuid.uuid4())
            supabase.table("channels").insert(data).execute()

        return {
            "message": "Número vinculado correctamente al cliente",
            "client_id": client_id,
            "whatsapp": full_value
        }

    except Exception as e:
        print(f"❌ Error en /link_whatsapp: {e}")
        raise HTTPException(status_code=500, detail=str(e))
