# api/create_client_if_needed.py

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class ClientPayload(BaseModel):
    auth_user_id: str
    email: str

@router.post("/create_or_get_client")
def create_or_get_client(payload: ClientPayload):
    try:
        print(f"🔵 Buscando cliente con user_id: {payload.auth_user_id}")
        result = supabase.table("clients").select("id").eq("user_id", payload.auth_user_id).execute()

        if result.data:
            client_id = result.data[0]["id"]
            print(f"✅ Cliente ya existe: {client_id}")
        else:
            name = payload.email.split("@")[0]
            print(f"🆕 Creando nuevo cliente para user_id: {payload.auth_user_id}")
            insert_res = supabase.table("clients").insert({
                "user_id": payload.auth_user_id,
                "name": name
            }).execute()

            if not insert_res or not insert_res.data:
                raise Exception("❌ Error al crear cliente")

            client_id = insert_res.data[0]["id"]
            print(f"🆕 Cliente creado: {client_id}")

        return JSONResponse(content={"client_id": client_id})

    except Exception as e:
        print("❌ Error en create_or_get_client:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
