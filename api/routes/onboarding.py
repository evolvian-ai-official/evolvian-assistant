# api/routes/onboarding.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()


# =========================
# Models
# =========================

class ProfileData(BaseModel):
    contact_name: str = Field(min_length=2)
    company_name: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    role: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    channels: Optional[List[str]] = []


class TermsData(BaseModel):
    accepted: bool
    accepted_marketing: bool = False


class CompleteOnboardingRequest(BaseModel):
    client_id: str
    profile: ProfileData
    terms: TermsData


# =========================
# Endpoint
# =========================

@router.post("/complete_onboarding")
async def complete_onboarding(
    payload: CompleteOnboardingRequest,
    request: Request
):
    try:
        now = datetime.now(timezone.utc).isoformat()

        client_id = payload.client_id

        if not client_id:
            raise HTTPException(status_code=400, detail="client_id required")

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # 🔹 UPSERT client_profile
        supabase.table("client_profile").upsert(
            {
                "client_id": client_id,
                "contact_name": payload.profile.contact_name,
                "company_name": payload.profile.company_name,
                "phone": payload.profile.phone,
                "industry": payload.profile.industry,
                "role": payload.profile.role,
                "country": payload.profile.country,
                "company_size": payload.profile.company_size,
                "channels": payload.profile.channels,
                "updated_at": now,
                "onboarding_completed": True,
                "onboarding_completed_at": now
            },
            on_conflict="client_id"
        ).execute()

        # 🔹 UPSERT client_terms_acceptance
        supabase.table("client_terms_acceptance").upsert(
            {
                "client_id": client_id,
                "accepted": payload.terms.accepted,
                "accepted_marketing": payload.terms.accepted_marketing,
                "accepted_at": now if payload.terms.accepted else None,
                "marketing_accepted_at": now if payload.terms.accepted_marketing else None,
                "version": "v1",
                "marketing_version": "v1",
                "ip_address": ip_address,
                "user_agent": user_agent
            },
            on_conflict="client_id"
        ).execute()

        return {
            "success": True,
            "message": "Onboarding completed successfully"
        }

    except Exception as e:
        print("❌ complete_onboarding error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
