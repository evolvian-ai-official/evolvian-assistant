from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class ConsentPayload(BaseModel):
    client_id: str
    email: str = ""
    phone: str = ""
    accepted_terms: bool
    consent_at: datetime

@router.post("/register_consent")
def register_consent(payload: ConsentPayload):
    try:
        response = supabase.table("widget_consents").insert({
            "client_id": payload.client_id,
            "email": payload.email,
            "phone": payload.phone,
            "accepted_terms": payload.accepted_terms,
            "consent_at": payload.consent_at.isoformat()
        }).execute()

        if response.data:
            return JSONResponse(content={"message": "Consentimiento registrado"}, status_code=200)
        else:
            raise HTTPException(status_code=500, detail="Error al registrar consentimiento")
    except Exception as e:
        print(f"❌ Error en /register_consent: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
