# api/clear_new_user_flag.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class ClearNewUserPayload(BaseModel):
    user_id: str

@router.post("/clear_new_user_flag")
def clear_new_user_flag(payload: ClearNewUserPayload):
    try:
        print(f"🧹 Limpiando bandera is_new_user para user: {payload.user_id}")

        # Actualizar la bandera en la tabla de users
        supabase.table("users").update({
            "is_new_user": False
        }).eq("id", payload.user_id).execute()

        return {"message": "✅ Bandera de nuevo usuario eliminada"}

    except Exception as e:
        print(f"❌ Error en /clear_new_user_flag: {e}")
        raise HTTPException(status_code=500, detail="Error al limpiar bandera")
