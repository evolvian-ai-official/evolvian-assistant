# api/initialize_user.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from modules.assistant_rag.supabase_client import (
    get_or_create_user,
    get_or_create_client_id,
    supabase
)

router = APIRouter()

class InitUserPayload(BaseModel):
    auth_user_id: str
    email: str

@router.post("/initialize_user")
def initialize_user(payload: InitUserPayload):
    try:
        # 1. Crear o recuperar user y client
        user_id = get_or_create_user(payload.auth_user_id, payload.email)
        client_id = get_or_create_client_id(user_id, payload.email)

        # 2. Verificar si ya existe configuración, uso o historial
        settings = supabase.table("client_settings")\
            .select("client_id")\
            .eq("client_id", client_id)\
            .execute()

        usage = supabase.table("client_usage")\
            .select("client_id")\
            .eq("client_id", client_id)\
            .execute()

        history = supabase.table("history")\
            .select("client_id")\
            .eq("client_id", client_id)\
            .limit(1)\
            .execute()

        user_record = supabase.table("users")\
            .select("created_at")\
            .eq("id", payload.auth_user_id)\
            .single()\
            .execute()

        now = datetime.now(timezone.utc)
        created_at = datetime.fromisoformat(user_record.data["created_at"])
        is_new_user = False

        if (not settings.data and not usage.data and not history.data) or (now - created_at < timedelta(minutes=5)):
            is_new_user = True

            # ✅ Guardar flag temporal
            supabase.table("users").update({
                "is_new_user": True
            }).eq("id", payload.auth_user_id).execute()

        # 🧩 Crear configuración inicial si no existe
        if not settings.data:
            supabase.table("client_settings").insert({
                "client_id": client_id,
                "plan": "free",
                "assistant_name": "Evolvian",
                "language": "es",
                "temperature": 0.7,
                "show_powered_by": True
            }).execute()

        # 🧩 Crear uso inicial si no existe
        if not usage.data:
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": 0,
                "documents_uploaded": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()

        return {
            "user_id": user_id,
            "client_id": client_id,
            "is_new_user": is_new_user
        }

    except Exception as e:
        print(f"❌ Error en /initialize_user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
