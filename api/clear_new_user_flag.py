# api/clear_new_user_flag.py

from fastapi import APIRouter, HTTPException, Request
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import get_current_user_id

router = APIRouter()

@router.post("/clear_new_user_flag")
def clear_new_user_flag(request: Request):
    try:
        auth_user_id = get_current_user_id(request)
        print(f"🧹 Limpiando bandera is_new_user para user: {auth_user_id}")

        # Actualizar la bandera en la tabla de users
        supabase.table("users").update({
            "is_new_user": False
        }).eq("id", auth_user_id).execute()

        return {"message": "✅ Bandera de nuevo usuario eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en /clear_new_user_flag: {e}")
        raise HTTPException(status_code=500, detail="Error al limpiar bandera")
