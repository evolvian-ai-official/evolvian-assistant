from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ClientProfilePayload(BaseModel):
    client_id: str
    industry: str
    role: str
    country: str
    channels: list[str]
    company_size: str

@router.post("/save_client_profile")
def save_client_profile(payload: ClientProfilePayload, request: Request):
    try:
        authorize_client_request(request, payload.client_id)
        data = payload.dict()

        # Upsert: crea o actualiza el perfil por client_id
        response = supabase.table("client_profile").upsert(
            data,
            on_conflict="client_id"
        ).execute()

        if response.data:
            return {"message": "✅ Perfil guardado exitosamente."}
        else:
            raise HTTPException(status_code=500, detail="Error al guardar perfil")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en POST /save_client_profile")
        raise HTTPException(status_code=500, detail="Error interno al guardar perfil")
