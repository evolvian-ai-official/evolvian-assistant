# api/link_channel.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.assistant_rag.supabase_client import (
    get_or_create_user,
    get_or_create_client_id,
    link_channel_to_client
)

router = APIRouter()

class WhatsAppLinkPayload(BaseModel):
    auth_user_id: str
    email: str
    phone: str  # solo número sin prefijo

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload):
    try:
        # 1. Crear o recuperar usuario
        user_id = get_or_create_user(payload.auth_user_id, payload.email)

        # 2. Crear o recuperar client_id vinculado a ese usuario
        client_id = get_or_create_client_id(user_id, payload.email)

        # 3. Formatear el canal (ej: whatsapp:+521...)
        full_value = f"whatsapp:+{payload.phone.lstrip('+')}"

        # 4. Vincular canal con client_id si no existe
        channel_id = link_channel_to_client(
            client_id=client_id,
            channel_type="whatsapp",
            value=full_value
        )

        return {
            "message": "Canal vinculado correctamente",
            "client_id": client_id,
            "channel_id": channel_id,
            "whatsapp": full_value
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
