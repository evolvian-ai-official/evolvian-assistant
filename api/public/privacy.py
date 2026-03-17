from datetime import datetime, timezone
from typing import Literal
import uuid
import re

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
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
    split_details_and_metadata,
)
from api.security.request_limiter import enforce_rate_limit, get_request_ip
from api.security.unsubscribe_client_id_crypto import decrypt_unsubscribe_client_id

router = APIRouter(prefix="/api/public/privacy", tags=["Public Privacy"])

CONSENT_LOG_TABLE = "public_privacy_consents"
PRIVACY_REQUEST_TABLE = "public_privacy_requests"


def _is_duplicate_contactame_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "duplicate" in message
        or "unique" in message
        or "23505" in message
        or "contactame_email_key" in message
    )


def _insert_contactame_with_fallbacks(
    *,
    primary_payload: dict,
    legacy_payload: dict | None = None,
    update_payload: dict | None = None,
    email: str,
) -> None:
    try:
        supabase.table("contactame").insert(primary_payload).execute()
        return
    except Exception as primary_error:
        if _is_duplicate_contactame_error(primary_error) and update_payload:
            supabase.table("contactame").update(update_payload).eq("email", email).execute()
            return
        if legacy_payload:
            try:
                supabase.table("contactame").insert(legacy_payload).execute()
                return
            except Exception as legacy_error:
                if _is_duplicate_contactame_error(legacy_error) and update_payload:
                    supabase.table("contactame").update(update_payload).eq("email", email).execute()
                    return
                raise legacy_error from primary_error
        raise


def _extract_opt_out_client_id(details: str | None) -> str | None:
    text_details, metadata = split_details_and_metadata(str(details or ""))
    scoped = str((metadata or {}).get("client_id") or "").strip()
    if scoped:
        return scoped
    match = re.search(r"\bclient_id=([a-f0-9-]{8,})\b", text_details, flags=re.IGNORECASE)
    if match:
        return str(match.group(1)).strip()
    return None


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
        legacy_fallback_record = {
            "name": name or "Privacy Request",
            "email": email,
            "subject": "Privacy request",
            "interested_plan": "Privacy",
            "message": fallback_message[:3900],
            "accepted_terms": True,
            "accepted_marketing": False,
            "terms_accepted_at": isoformat_utc(submitted_at),
            "source": "privacy_request",
        }
        try:
            _insert_contactame_with_fallbacks(
                primary_payload=fallback_record,
                legacy_payload=legacy_fallback_record,
                update_payload={
                    "subject": "Privacy request",
                    "interested_plan": "Privacy",
                    "message": fallback_message[:3900],
                    "accepted_terms": True,
                    "accepted_marketing": False,
                    "terms_accepted_at": isoformat_utc(submitted_at),
                    "source": "privacy_request",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
                email=email,
            )
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


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_marketing_email(
    request: Request,
    email: EmailStr = Query(...),
    client_id: str | None = Query(None),
    language: Literal["en", "es"] = Query("en"),
):
    request_ip = get_request_ip(request)
    enforce_rate_limit(
        scope="privacy_unsubscribe_ip",
        key=request_ip,
        limit=60,
        window_seconds=300,
    )

    normalized_email = str(email).strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required.")
    raw_client_id = str(client_id or "").strip()
    resolved_client_id = decrypt_unsubscribe_client_id(raw_client_id)
    if raw_client_id and not resolved_client_id:
        raise HTTPException(status_code=400, detail="invalid_client_id_token")

    try:
        existing = (
            supabase.table(PRIVACY_REQUEST_TABLE)
            .select("id,status,created_at,details")
            .eq("email", normalized_email)
            .eq("request_type", "marketing_opt_out")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        existing_rows = existing.data or []
    except Exception:
        existing_rows = []

    latest_applicable = None
    for row in existing_rows:
        scoped_client_id = _extract_opt_out_client_id((row or {}).get("details"))
        if resolved_client_id and scoped_client_id and str(scoped_client_id) != str(resolved_client_id):
            continue
        latest_applicable = row or {}
        break

    existing_status = str((latest_applicable or {}).get("status") or "").strip().lower()
    has_active_opt_out = bool(latest_applicable) and existing_status not in {"withdrawn", "denied"}

    if not has_active_opt_out:
        submitted_at = now_utc()
        due_at = calculate_due_at(submitted_at)
        request_id = f"dsar_{uuid.uuid4().hex[:12]}"
        dsar_metadata = build_initial_metadata(
            request_id=request_id,
            request_type="marketing_opt_out",
            submitted_at=submitted_at,
            due_at=due_at,
            source="email_unsubscribe_link",
        )
        if resolved_client_id:
            dsar_metadata["client_id"] = str(resolved_client_id).strip()
        details = "One-click marketing unsubscribe from campaign email."
        details_with_metadata = combine_details_and_metadata(details, dsar_metadata)

        record = {
            "name": None,
            "email": normalized_email,
            "request_type": "marketing_opt_out",
            "details": details_with_metadata,
            "language": language,
            "consent_version": "2026-02",
            "source": "email_unsubscribe_link",
            "status": "pending",
            "ip_address": request_ip,
            "user_agent": request.headers.get("user-agent"),
            "created_at": isoformat_utc(submitted_at),
        }
        try:
            supabase.table(PRIVACY_REQUEST_TABLE).insert(record).execute()
        except Exception as insert_error:
            print(
                f"⚠️ Failed recording marketing unsubscribe | email={normalized_email} | client_id={resolved_client_id or 'none'} | error={insert_error}"
            )
            # In race/duplicate scenarios, an active opt-out may already exist.
            try:
                retry_existing = (
                    supabase.table(PRIVACY_REQUEST_TABLE)
                    .select("id,status,created_at,details")
                    .eq("email", normalized_email)
                    .eq("request_type", "marketing_opt_out")
                    .order("created_at", desc=True)
                    .limit(50)
                    .execute()
                )
                retry_rows = retry_existing.data or []
            except Exception:
                retry_rows = []

            retry_latest = None
            for row in retry_rows:
                scoped_client_id = _extract_opt_out_client_id((row or {}).get("details"))
                if resolved_client_id and scoped_client_id and str(scoped_client_id) != str(resolved_client_id):
                    continue
                retry_latest = row or {}
                break

            retry_status = str((retry_latest or {}).get("status") or "").strip().lower()
            retry_has_active_opt_out = bool(retry_latest) and retry_status not in {"withdrawn", "denied"}
            if not retry_has_active_opt_out:
                fallback_message = (
                    f"Request ID: {request_id}\n"
                    "Privacy request type: marketing_opt_out\n"
                    f"Submitted at: {isoformat_utc(submitted_at)}\n"
                    f"Due at: {isoformat_utc(due_at)}\n"
                    f"Language: {language}\n"
                    f"Client ID: {resolved_client_id or 'N/A'}\n"
                    "Details: One-click marketing unsubscribe from campaign email."
                )
                fallback_record = {
                    "name": "Unsubscribe request",
                    "email": normalized_email,
                    "subject": "Marketing unsubscribe request",
                    "interested_plan": "Privacy",
                    "message": fallback_message[:3900],
                    "accepted_terms": True,
                    "accepted_marketing": False,
                    "terms_accepted_at": isoformat_utc(submitted_at),
                    "source": "privacy_unsubscribe_fallback",
                    "ip_address": request_ip,
                    "user_agent": request.headers.get("user-agent"),
                }
                legacy_fallback_record = {
                    "name": "Unsubscribe request",
                    "email": normalized_email,
                    "subject": "Marketing unsubscribe request",
                    "interested_plan": "Privacy",
                    "message": fallback_message[:3900],
                    "accepted_terms": True,
                    "accepted_marketing": False,
                    "terms_accepted_at": isoformat_utc(submitted_at),
                    "source": "privacy_unsubscribe_fallback",
                }
                try:
                    _insert_contactame_with_fallbacks(
                        primary_payload=fallback_record,
                        legacy_payload=legacy_fallback_record,
                        update_payload={
                            "subject": "Marketing unsubscribe request",
                            "interested_plan": "Privacy",
                            "message": fallback_message[:3900],
                            "accepted_terms": True,
                            "accepted_marketing": False,
                            "terms_accepted_at": isoformat_utc(submitted_at),
                            "source": "privacy_unsubscribe_fallback",
                            "ip_address": request_ip,
                            "user_agent": request.headers.get("user-agent"),
                        },
                        email=normalized_email,
                    )
                except Exception as fallback_error:
                    if language == "es":
                        fail_title = "No se pudo completar la baja"
                        fail_body = "No pudimos registrar tu solicitud de baja. Intenta de nuevo en unos minutos."
                    else:
                        fail_title = "Unsubscribe could not be completed"
                        fail_body = "We could not record your unsubscribe request. Please try again in a few minutes."

                    print(
                        f"⚠️ Failed unsubscribe fallback | email={normalized_email} | client_id={resolved_client_id or 'none'} | error={fallback_error}"
                    )
                    fail_html = (
                        "<!doctype html><html><head><meta charset='utf-8'/>"
                        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
                        f"<title>{fail_title}</title></head>"
                        "<body style='font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:24px;'>"
                        "<div style='max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;'>"
                        f"<h2 style='margin:0 0 10px;color:#0f172a;'>{fail_title}</h2>"
                        f"<p style='margin:0;color:#334155;line-height:1.6;'>{fail_body}</p>"
                        "</div></body></html>"
                    )
                    return HTMLResponse(content=fail_html, status_code=503)

    if language == "es":
        title = "Has sido dado de baja"
        body = "Tu solicitud para dejar de recibir correos de marketing fue registrada."
    else:
        title = "You are unsubscribed"
        body = "Your request to opt out from marketing emails has been recorded."

    html = (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        f"<title>{title}</title></head>"
        "<body style='font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:24px;'>"
        "<div style='max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;'>"
        f"<h2 style='margin:0 0 10px;color:#0f172a;'>{title}</h2>"
        f"<p style='margin:0;color:#334155;line-height:1.6;'>{body}</p>"
        "</div></body></html>"
    )
    return HTMLResponse(content=html, status_code=200)


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
