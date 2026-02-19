# api/create_client_if_needed.py

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)

class ClientPayload(BaseModel):
    auth_user_id: str | None = None
    email: str

@router.post("/create_or_get_client")
def create_or_get_client(payload: ClientPayload, request: Request):
    try:
        auth_user_id = get_current_user_id(request)
        if payload.auth_user_id and payload.auth_user_id != auth_user_id:
            raise HTTPException(status_code=403, detail="forbidden_user_mismatch")

        result = supabase.table("clients").select("id").eq("user_id", auth_user_id).execute()

        if result.data:
            client_id = result.data[0]["id"]
        else:
            name = payload.email.split("@")[0]
            insert_res = supabase.table("clients").insert({
                "user_id": auth_user_id,
                "name": name
            }).execute()

            if not insert_res or not insert_res.data:
                raise Exception("❌ Error al crear cliente")

            client_id = insert_res.data[0]["id"]

        return JSONResponse(content={"client_id": client_id})

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en create_or_get_client")
        return JSONResponse(status_code=500, content={"error": "create_or_get_client_failed"})
