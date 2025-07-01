# api/user_flags.py (extendido con GET)

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

@router.post("/clear_new_user_flag")
def clear_new_user_flag(user_id: str = Query(...)):
    try:
        supabase.table("users").update({
            "is_new_user": None
        }).eq("id", user_id).execute()

        return JSONResponse(content={"message": "✅ Bandera de nuevo usuario eliminada"})

    except Exception as e:
        print(f"❌ Error al limpiar is_new_user: {e}")
        raise HTTPException(status_code=500, detail="Error al limpiar bandera de nuevo usuario")


@router.get("/is_new_user_flag")
def is_new_user_flag(user_id: str = Query(...)):
    try:
        response = supabase.table("users").select("is_new_user").eq("id", user_id).single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return JSONResponse(content={
            "user_id": user_id,
            "is_new_user": response.data.get("is_new_user", False)
        })

    except Exception as e:
        print(f"❌ Error en /is_new_user_flag: {e}")
        raise HTTPException(status_code=500, detail="Error al consultar estado de nuevo usuario")
