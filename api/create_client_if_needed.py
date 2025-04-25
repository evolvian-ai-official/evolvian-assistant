# api/create_client_if_needed.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class ClientPayload(BaseModel):
    auth_user_id: str
    email: str

@router.post("/create_or_get_client")
def create_or_get_client(payload: ClientPayload):
    try:
        result = supabase.table("clients").select("id").eq("auth_user_id", payload.auth_user_id).execute()
        if result.data:
            client_id = result.data[0]["id"]
            print(f"✅ Cliente ya existe: {client_id}")
        else:
            name = payload.email.split("@")[0]
            insert_res = supabase.table("clients").insert({
                "auth_user_id": payload.auth_user_id,
                "name": name
            }).execute()
            client_id = insert_res.data[0]["id"]
            print(f"🆕 Cliente creado: {client_id}")
        return JSONResponse(content={"client_id": client_id})
    except Exception as e:
        print("❌ Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
