from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
import uuid

router = APIRouter()

class WhatsAppLinkPayload(BaseModel):
    auth_user_id: str
    email: str
    phone: str  # Puede venir como 'whatsapp:+...' o solo el número
    provider: str = "meta"
    wa_phone_id: str | None = None
    wa_token: str | None = None

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload):
    try:
        print("🔗 Vinculando número de WhatsApp...")

        # 1. Buscar usuario
        user_res = supabase.table("users")\
            .select("id")\
            .eq("id", payload.auth_user_id)\
            .single()\
            .execute()

        if not user_res or not user_res.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_id = user_res.data["id"]
        print(f"✅ Usuario encontrado: {user_id}")

        # 2. Buscar cliente asociado
        client_res = supabase.table("clients")\
            .select("id")\
            .eq("user_id", user_id)\
            .single()\
            .execute()

        if not client_res or not client_res.data:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        client_id = client_res.data["id"]
        print(f"✅ Cliente asociado: {client_id}")

        # 3. Sanitizar número y usar formato oficial
        number = payload.phone.replace("whatsapp:", "").lstrip("+")
        full_value = f"whatsapp:+{number}"
        print(f"📞 Formato final del número: {full_value}")

        # 4. Buscar canal existente
        existing = supabase.table("channels")\
            .select("id, client_id")\
            .eq("type", "whatsapp")\
            .eq("value", full_value)\
            .maybe_single()\
            .execute()

        if existing and existing.data:
            existing_client = existing.data["client_id"]
            if existing_client != client_id:
                print("🚫 Este número ya está vinculado a otro cliente")
                raise HTTPException(
                    status_code=409,
                    detail="Este número de WhatsApp ya está vinculado a otro cliente"
                )

            print("🔁 Canal existente. Actualizando credenciales...")
            supabase.table("channels")\
                .update({
                    "provider": payload.provider,
                    "wa_phone_id": payload.wa_phone_id,
                    "wa_token": payload.wa_token,
                })\
                .eq("id", existing.data["id"])\
                .execute()
        else:
            print("🆕 Canal nuevo. Insertando...")
            supabase.table("channels").insert({
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "type": "whatsapp",
                "value": full_value,
                "provider": payload.provider,
                "wa_phone_id": payload.wa_phone_id,
                "wa_token": payload.wa_token,
            }).execute()

        return {
            "message": "✅ Número vinculado correctamente al cliente",
            "client_id": client_id,
            "whatsapp": full_value
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error en /link_whatsapp: {e}")
        raise HTTPException(status_code=500, detail=str(e))
