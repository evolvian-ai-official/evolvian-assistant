from datetime import datetime, timezone
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.config.config import supabase
from api.privacy_dsr import (
    build_initial_metadata,
    calculate_due_at,
    combine_details_and_metadata,
    ensure_request_metadata,
    get_due_at_from_metadata,
    isoformat_utc,
    now_utc,
)
from api.security.request_limiter import enforce_rate_limit, get_request_ip

router = APIRouter(prefix="/api/public/privacy", tags=["Public Privacy"])

CONSENT_LOG_TABLE = "public_privacy_consents"
PRIVACY_REQUEST_TABLE = "public_privacy_requests"


class PrivacyConsentPayload(BaseModel):
    consent_version: str = Field(default="2026-02", min_length=2, max_length=40)
    language: Literal["en", "es"] = "en"
    necessary: bool = True
    analytics: bool = False
    marketing: bool = False
    sale_share_opt_out: bool = False
    global_privacy_control: bool = False
    source_path: str = Field(default="/", min_length=1, max_length=250)


class PrivacyRequestPayload(BaseModel):
    name: str = Field(default="", max_length=160)
    email: EmailStr
    request_type: Literal["access", "delete", "correct", "opt_out_sale_share", "marketing_opt_out"]
    details: str = Field(default="", max_length=4000)
    language: Literal["en", "es"] = "en"
    consent_version: str = Field(default="2026-02", min_length=2, max_length=40)


@router.post("/consent")
def log_privacy_consent(payload: PrivacyConsentPayload, request: Request):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "source": "public_page",
        "consent_version": payload.consent_version,
        "language": payload.language,
        "necessary": True,
        "analytics": bool(payload.analytics),
        "marketing": bool(payload.marketing),
        "sale_share_opt_out": bool(payload.sale_share_opt_out),
        "global_privacy_control": bool(payload.global_privacy_control),
        "source_path": payload.source_path,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": now,
    }

    try:
        supabase.table(CONSENT_LOG_TABLE).insert(record).execute()
        return {"logged": True}
    except Exception as error:
        print(f"⚠️ Privacy consent log skipped ({CONSENT_LOG_TABLE} unavailable): {error}")
        return {"logged": False}


@router.post("/request")
def submit_privacy_request(payload: PrivacyRequestPayload, request: Request):
    request_ip = get_request_ip(request)
    enforce_rate_limit(
        scope="privacy_request_ip",
        key=request_ip,
        limit=20,
        window_seconds=300,
    )

    email = str(payload.email).strip().lower()
    name = payload.name.strip()
    details = payload.details.strip()
    ip_address = request_ip
    user_agent = request.headers.get("user-agent")
    submitted_at = now_utc()
    due_at = calculate_due_at(submitted_at)
    request_id = f"dsar_{uuid.uuid4().hex[:12]}"

    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")

    dsar_metadata = build_initial_metadata(
        request_id=request_id,
        request_type=payload.request_type,
        submitted_at=submitted_at,
        due_at=due_at,
        source="public_page",
    )
    details_with_metadata = combine_details_and_metadata(details, dsar_metadata)

    request_record = {
        "name": name or None,
        "email": email,
        "request_type": payload.request_type,
        "details": details_with_metadata or None,
        "language": payload.language,
        "consent_version": payload.consent_version,
        "source": "public_page",
        "status": "pending",
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": isoformat_utc(submitted_at),
    }

    try:
        supabase.table(PRIVACY_REQUEST_TABLE).insert(request_record).execute()
        return {
            "message": "Privacy request submitted successfully.",
            "request_id": request_id,
            "submitted_at": isoformat_utc(submitted_at),
            "due_at": isoformat_utc(due_at),
            "status": "pending",
        }
    except Exception as primary_error:
        print(f"⚠️ Privacy request table unavailable, fallback to contactame: {primary_error}")
        fallback_message = (
            f"Request ID: {request_id}\n"
            f"Privacy request type: {payload.request_type}\n"
            f"Submitted at: {isoformat_utc(submitted_at)}\n"
            f"Due at: {isoformat_utc(due_at)}\n"
            f"Language: {payload.language}\n"
            f"Consent version: {payload.consent_version}\n"
            f"Details: {details or 'N/A'}"
        )
        fallback_record = {
            "name": name or "Privacy Request",
            "email": email,
            "subject": "Privacy request",
            "interested_plan": "Privacy",
            "message": fallback_message[:3900],
            "accepted_terms": True,
            "accepted_marketing": False,
            "terms_accepted_at": isoformat_utc(submitted_at),
            "source": "privacy_request",
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        try:
            supabase.table("contactame").insert(fallback_record).execute()
            return {
                "message": "Privacy request submitted successfully.",
                "request_id": request_id,
                "submitted_at": isoformat_utc(submitted_at),
                "due_at": isoformat_utc(due_at),
                "status": "pending",
            }
        except Exception as fallback_error:
            raise HTTPException(
                status_code=500,
                detail=f"Could not submit privacy request: {fallback_error}",
            ) from fallback_error


@router.get("/request/status")
def get_privacy_request_status(email: EmailStr, request_id: str, request: Request):
    request_ip = get_request_ip(request)
    enforce_rate_limit(
        scope="privacy_request_status_ip",
        key=request_ip,
        limit=40,
        window_seconds=300,
    )

    normalized_email = str(email).strip().lower()
    normalized_request_id = request_id.strip().lower()
    if not normalized_request_id.startswith("dsar_"):
        raise HTTPException(status_code=400, detail="invalid_request_id")

    try:
        rows = (
            supabase.table(PRIVACY_REQUEST_TABLE)
            .select("id, request_type, status, details, created_at")
            .eq("email", normalized_email)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"privacy_request_unavailable: {error}") from error

    for row in rows.data or []:
        record = row if isinstance(row, dict) else {}
        row_id = str(record.get("id") or "")
        record_request_id = row_id
        if row_id:
            record_request_id = f"dsar_{row_id.replace('-', '')[:12]}".lower()
        _, metadata = ensure_request_metadata(record=record, request_id=record_request_id)
        if str(metadata.get("request_id") or "").lower() != normalized_request_id:
            continue

        due_at = get_due_at_from_metadata(metadata, created_at=record.get("created_at"))
        return {
            "request_id": metadata.get("request_id"),
            "request_type": metadata.get("request_type") or record.get("request_type"),
            "status": metadata.get("status") or record.get("status") or "pending",
            "verification_status": metadata.get("verification_status", "pending"),
            "submitted_at": metadata.get("submitted_at") or record.get("created_at"),
            "due_at": isoformat_utc(due_at),
        }

    raise HTTPException(status_code=404, detail="privacy_request_not_found")
