from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.assistant_rag.supabase_client import supabase
from datetime import datetime

router = APIRouter()

class AcceptTermsPayload(BaseModel):
    client_id: str

@router.post("/accept_terms")
def accept_terms(payload: AcceptTermsPayload):
    try:
        client_id = payload.client_id
        consent_at = datetime.utcnow().isoformat()

        response = supabase.table("client_terms_acceptance").upsert({
            "client_id": client_id,
            "accepted_terms": True,
            "consent_at": consent_at
        }, on_conflict="client_id").execute()

        if response.data:
            return {"message": "✅ Terms aceptados correctamente en client_terms_acceptance."}
        else:
            raise HTTPException(status_code=500, detail="Error al guardar aceptación de términos")

    except Exception as e:
        print(f"❌ Error en POST /accept_terms: {e}")
        raise HTTPException(status_code=500, detail="Error interno al aceptar términos")
