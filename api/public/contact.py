from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone

from api.config.config import supabase
from api.compliance.marketing_consent_adapter import record_marketing_consent

router = APIRouter(prefix="/api/public", tags=["Public Contact"])

ALLOWED_PLANS = {"free", "starter", "premium", "white label"}


class PublicContactPayload(BaseModel):
    name: str
    email: EmailStr
    subject: str
    plan: str
    usage: str
    accepted_terms: bool
    accepted_privacy: bool
    accepted_marketing: bool = False
    consent_version: str | None = None


@router.post("/contact")
def create_public_contact(payload: PublicContactPayload, request: Request):
    name = payload.name.strip()
    email = str(payload.email).strip().lower()
    subject = payload.subject.strip() or "Website inquiry"
    plan = payload.plan.strip()
    usage = payload.usage.strip()
    plan_normalized = plan.lower()

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must have at least 2 characters.")
    if len(usage) < 10:
        raise HTTPException(status_code=400, detail="Message must have at least 10 characters.")
    if not payload.accepted_terms:
        raise HTTPException(status_code=400, detail="Terms & Conditions must be accepted.")
    if not payload.accepted_privacy:
        raise HTTPException(status_code=400, detail="Privacy Policy must be accepted.")

    if plan_normalized not in ALLOWED_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        existing_contact = (
            supabase.table("contactame")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if existing_contact.data:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_EMAIL",
                    "message": (
                        "Ya tenemos tu email registrado. Mandanos un email a sales@evolvianai.com "
                        "o chatea con Evolvian Assistant abriendo el icono a tu derecha."
                    ),
                },
            )

        accepted_at = datetime.now(timezone.utc).isoformat()
        insert_payload = {
            "name": name,
            "email": email,
            "subject": subject,
            "interested_plan": plan,
            "message": usage,
            "accepted_terms": True,
            "accepted_privacy_policy": True,
            "accepted_marketing": bool(payload.accepted_marketing),
            "terms_accepted_at": accepted_at,
            "privacy_accepted_at": accepted_at,
            "consent_version": payload.consent_version,
            "marketing_optin_at": datetime.now(timezone.utc).isoformat() if payload.accepted_marketing else None,
            "source": "public_page",
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        legacy_insert_payload = {
            "name": name,
            "email": email,
            "subject": subject,
            "interested_plan": plan,
            "message": usage,
            "accepted_terms": True,
            "accepted_marketing": bool(payload.accepted_marketing),
            "terms_accepted_at": accepted_at,
            "marketing_optin_at": datetime.now(timezone.utc).isoformat() if payload.accepted_marketing else None,
            "source": "public_page",
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        try:
            supabase.table("contactame").insert(insert_payload).execute()
        except Exception as insert_error:
            msg = str(insert_error).lower()
            if (
                "accepted_privacy_policy" in msg
                or "privacy_accepted_at" in msg
                or "consent_version" in msg
            ):
                supabase.table("contactame").insert(legacy_insert_payload).execute()
            else:
                raise

        if payload.accepted_marketing:
            existing = (
                supabase.table("newsletter_subscribers")
                .select("id")
                .eq("email", email)
                .execute()
            )

            if existing.data:
                (
                    supabase.table("newsletter_subscribers")
                    .update(
                        {
                            "name": name,
                            "source": "contact_form",
                            "accepted_marketing": True,
                            "accepted_privacy_policy": True,
                        }
                    )
                    .eq("email", email)
                    .execute()
                )
            else:
                (
                    supabase.table("newsletter_subscribers")
                    .insert(
                        {
                            "name": name,
                            "email": email,
                            "source": "contact_form",
                            "ip_address": ip_address,
                            "user_agent": user_agent,
                            "accepted_marketing": True,
                            "accepted_privacy_policy": True,
                        }
                    )
                    .execute()
                )

            # Canonical outbound consent snapshot (best effort).
            record_marketing_consent(
                source="public_contact_form",
                email=email,
                phone=None,
                accepted_terms=True,
                accepted_email_marketing=True,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return {"message": "Contact request saved successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save contact request: {e}")
