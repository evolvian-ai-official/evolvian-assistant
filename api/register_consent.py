from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from supabase import create_client
from utils.supabase_client import supabase

from uuid import UUID
from datetime import datetime

router = APIRouter()

class ConsentInput(BaseModel):
    client_id: UUID
    email: EmailStr | None = None
    phone: str | None = None
    accepted_terms: bool | None = None
    consent_at: datetime

@router.post("/register_consent")
async def register_consent(data: ConsentInput, request: Request):
    # Validar existencia de client_id
    client_check = supabase.from_("clients").select("id").eq("id", str(data.client_id)).single().execute()
    if client_check.error:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Insertar consentimiento
    result = supabase.from_("widget_consents").insert({
        "client_id": str(data.client_id),
        "email": data.email,
        "phone": data.phone,
        "accepted_terms": data.accepted_terms,
        "consent_at": data.consent_at.isoformat(),
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent")
    }).execute()

    if result.error:
        raise HTTPException(status_code=500, detail="Failed to register consent")

    return {"message": "Consent registered successfully"}
