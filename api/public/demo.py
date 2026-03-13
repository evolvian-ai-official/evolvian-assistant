from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from api.config.config import supabase
from api.compliance.marketing_consent_adapter import record_marketing_consent

router = APIRouter(prefix="/api/public", tags=["Public Demo"])


class DemoLeadPayload(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    accepted_terms: bool
    accepted_marketing: bool = False
    consent_version: str | None = None


class DemoFeedbackPayload(BaseModel):
    message: str
    email: EmailStr | None = None
    phone: str | None = None
    language: str | None = None


@router.post("/demo/lead")
def register_demo_lead(payload: DemoLeadPayload, request: Request):
    name = payload.name.strip()
    email = str(payload.email).strip().lower()
    phone = (payload.phone or "").strip() or None

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must have at least 2 characters.")
    if not payload.accepted_terms:
        raise HTTPException(status_code=400, detail="Terms & Conditions must be accepted.")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        if payload.accepted_marketing:
            existing = (
                supabase
                .table("newsletter_subscribers")
                .select("id")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            if existing.data:
                (
                    supabase
                    .table("newsletter_subscribers")
                    .update(
                        {
                            "name": name,
                            "source": "demo",
                            "accepted_marketing": True,
                            "accepted_privacy_policy": True,
                            "user_agent": user_agent,
                            "ip_address": ip_address,
                        }
                    )
                    .eq("email", email)
                    .execute()
                )
            else:
                (
                    supabase
                    .table("newsletter_subscribers")
                    .insert(
                        {
                            "name": name,
                            "email": email,
                            "source": "demo",
                            "consented_at": datetime.now(timezone.utc).isoformat(),
                            "accepted_marketing": True,
                            "accepted_privacy_policy": True,
                            "ip_address": ip_address,
                            "user_agent": user_agent,
                        }
                    )
                    .execute()
                )

            record_marketing_consent(
                source="public_demo",
                email=email,
                phone=phone,
                accepted_terms=True,
                accepted_email_marketing=True,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return {
            "success": True,
            "accepted_marketing": bool(payload.accepted_marketing),
            "consent_version": payload.consent_version,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to register demo lead: {error}")


@router.post("/demo/feedback")
def submit_demo_feedback(payload: DemoFeedbackPayload, request: Request):
    message = (payload.message or "").strip()
    if len(message) < 10:
        raise HTTPException(status_code=400, detail="Feedback must have at least 10 characters.")

    submitted_at = datetime.now(timezone.utc).isoformat()
    email = str(payload.email).strip().lower() if payload.email else None
    phone = (payload.phone or "").strip() or None
    language = (payload.language or "").strip().lower() or "en"
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    fallback_email = f"demo-feedback+{uuid4().hex[:12]}@evolvian.local"
    record_email = email or fallback_email

    feedback_message = (
        f"Demo feedback submitted at: {submitted_at}\n"
        f"Language: {language}\n"
        f"Phone: {phone or 'N/A'}\n\n"
        f"{message}"
    )

    insert_payload = {
        "name": "Demo Feedback",
        "email": record_email,
        "subject": "Demo feedback",
        "interested_plan": "Demo",
        "message": feedback_message[:3900],
        "accepted_terms": True,
        "accepted_marketing": False,
        "terms_accepted_at": submitted_at,
        "source": "public_demo_feedback",
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    try:
        supabase.table("contactame").insert(insert_payload).execute()
        return {"message": "Feedback saved successfully."}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to save demo feedback: {error}")
