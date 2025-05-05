from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class ClientProfilePayload(BaseModel):
    client_id: str
    industry: str
    role: str
    country: str
    channels: list[str]
    company_size: str

@router.post("/save_client_profile")
def save_client_profile(payload: ClientProfilePayload):
    try:
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

    except Exception as e:
        print(f"❌ Error en POST /save_client_profile: {e}")
        raise HTTPException(status_code=500, detail="Error interno al guardar perfil")
