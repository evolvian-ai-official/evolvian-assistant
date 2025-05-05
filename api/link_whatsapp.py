# api/link_whatsapp.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
import uuid

router = APIRouter()

class WhatsAppLinkPayload(BaseModel):
    auth_user_id: str
    email: str
    phone: str  # sin "whatsapp:" al principio

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

        # 3. Formatear valor del canal
        full_value = f"whatsapp:+{payload.phone.lstrip('+')}"

        # 4. Buscar si ya existe ese canal
        existing = supabase.table("channels")\
            .select("id")\
            .eq("type", "whatsapp")\
            .eq("value", full_value)\
            .execute()

        if existing.data and len(existing.data) > 0:
            # Actualizar si ya existe
            update_res = supabase.table("channels")\
                .update({
                    "client_id": client_id
                })\
                .eq("id", existing.data[0]["id"])\
                .execute()
        else:
            # Insertar si no existe
            insert_res = supabase.table("channels").insert({
                "id": str(uuid.uuid4()),
                "type": "whatsapp",
                "value": full_value,
                "client_id": client_id
            }).execute()

        return {
            "message": "Número vinculado correctamente al cliente",
            "client_id": client_id,
            "whatsapp": full_value
        }

    except Exception as e:
        print(f"❌ Error en /link_whatsapp: {e}")
        raise HTTPException(status_code=500, detail=str(e))
