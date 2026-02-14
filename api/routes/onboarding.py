# api/routes/onboarding.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from zoneinfo import available_timezones
import logging

from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


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
    timezone: Optional[str] = "UTC"


class TermsData(BaseModel):
    accepted: bool
    accepted_marketing: bool = False


class CompleteOnboardingRequest(BaseModel):
    client_id: str
    profile: ProfileData
    terms: TermsData


# =========================
# Complete Onboarding
# =========================

@router.post("/complete_onboarding")
async def complete_onboarding(
    payload: CompleteOnboardingRequest,
    request: Request
):
    now = datetime.now(timezone.utc)

    try:
        client_id = payload.client_id
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id required")

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # 🔒 Validate timezone
        timezone_value = payload.profile.timezone or "UTC"

        if timezone_value not in available_timezones():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timezone: {timezone_value}"
            )

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
                "updated_at": now.isoformat(),
                "onboarding_completed": True,
                "onboarding_completed_at": now.isoformat()
            },
            on_conflict="client_id"
        ).execute()

        # 🔹 Update ONLY timezone in client_settings
        supabase.table("client_settings").update(
            {
                "timezone": timezone_value,
                "updated_at": now.isoformat(),
            }
        ).eq("client_id", client_id).execute()

        # 🔹 UPSERT client_terms_acceptance
        supabase.table("client_terms_acceptance").upsert(
            {
                "client_id": client_id,
                "accepted": payload.terms.accepted,
                "accepted_marketing": payload.terms.accepted_marketing,
                "accepted_at": now.isoformat() if payload.terms.accepted else None,
                "marketing_accepted_at": now.isoformat() if payload.terms.accepted_marketing else None,
                "version": "v1",
                "marketing_version": "v1",
                "ip_address": ip_address,
                "user_agent": user_agent
            },
            on_conflict="client_id"
        ).execute()

        logger.info(f"✅ Onboarding completed for client {client_id}")

        return {
            "success": True,
            "message": "Onboarding completed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ complete_onboarding failed")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# =========================
# Get Profile
# =========================

@router.get("/profile/{client_id}")
async def get_profile(client_id: str):

    try:
        # 🔹 Profile
        profile_res = (
            supabase
            .table("client_profile")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        profile_data = profile_res.data[0] if profile_res.data else None

        # 🔹 Terms
        terms_res = (
            supabase
            .table("client_terms_acceptance")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        terms_data = terms_res.data[0] if terms_res.data else None

        # 🔹 Settings (timezone)
        settings_res = (
            supabase
            .table("client_settings")
            .select("timezone")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        timezone_value = (
            settings_res.data[0]["timezone"]
            if settings_res.data and settings_res.data[0].get("timezone")
            else "UTC"
        )

        return {
            "profile": profile_data,
            "terms": terms_data,
            "timezone": timezone_value
        }

    except Exception as e:
        logger.exception("❌ Failed to fetch profile")
        raise HTTPException(status_code=500, detail="Internal Server Error")
