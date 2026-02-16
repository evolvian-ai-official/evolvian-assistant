# api/user_flags.py (extendido con GET)

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import get_current_user_id

router = APIRouter()

@router.post("/clear_new_user_flag")
def clear_new_user_flag(request: Request, user_id: Optional[str] = Query(None)):
    try:
        auth_user_id = get_current_user_id(request)
        target_user_id = user_id or auth_user_id
        if target_user_id != auth_user_id:
            raise HTTPException(status_code=403, detail="forbidden_user_access")
        supabase.table("users").update({
            "is_new_user": None
        }).eq("id", target_user_id).execute()

        return JSONResponse(content={"message": "✅ Bandera de nuevo usuario eliminada"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al limpiar is_new_user: {e}")
        raise HTTPException(status_code=500, detail="Error al limpiar bandera de nuevo usuario")


@router.get("/is_new_user_flag")
def is_new_user_flag(request: Request, user_id: Optional[str] = Query(None)):
    try:
        auth_user_id = get_current_user_id(request)
        target_user_id = user_id or auth_user_id
        if target_user_id != auth_user_id:
            raise HTTPException(status_code=403, detail="forbidden_user_access")
        response = (
            supabase.table("users")
            .select("is_new_user")
            .eq("id", target_user_id)
            .single()
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return JSONResponse(content={
            "user_id": target_user_id,
            "is_new_user": response.data.get("is_new_user", False)
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en /is_new_user_flag: {e}")
        raise HTTPException(status_code=500, detail="Error al consultar estado de nuevo usuario")
