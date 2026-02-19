# api/terms_api.py
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import os
from api.modules.assistant_rag.supabase_client import supabase  # ✅ import corregido
from api.authz import authorize_client_request

router = APIRouter()


def _parse_accepted_at(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _terms_valid_days() -> int:
    raw = (os.getenv("TERMS_ACCEPTANCE_VALID_DAYS") or "0").strip()
    try:
        days = int(raw)
    except ValueError:
        return 0
    return max(0, days)

# 📦 Modelo para payload de aceptación
class AcceptTermsPayload(BaseModel):
    client_id: str


# 🧭 GET — Verificar si el cliente ya aceptó los términos
@router.get("/accepted_terms")
def check_accepted_terms(request: Request, client_id: str = Query(...)):
    """
    Checks if the client has accepted the Terms & Conditions.
    Returns acceptance status, date, and version.
    """
    try:
        authorize_client_request(request, client_id)
        response = (
            supabase.table("client_terms_acceptance")
            .select("client_id, accepted_at, version, accepted")
            .eq("client_id", client_id)
            .order("accepted_at", desc=True)
            .limit(20)
            .execute()
        )

        # 🚫 No hay registro → nunca aceptó
        if not response.data or len(response.data) == 0:
            return JSONResponse(content={"has_accepted": False, "reason": "not_found"})

        records = response.data
        accepted_record = next((r for r in records if bool(r.get("accepted"))), records[0])
        accepted = bool(accepted_record.get("accepted"))
        accepted_at = accepted_record.get("accepted_at")
        version = accepted_record.get("version", "v1")
        validity_days = _terms_valid_days()

        if accepted and validity_days > 0:
            accepted_dt = _parse_accepted_at(accepted_at)
            if not accepted_dt:
                # If a legacy timestamp can't be parsed, avoid locking users into repeated modal loops.
                return JSONResponse(
                    content={
                        "has_accepted": True,
                        "accepted_at": accepted_at,
                        "version": version,
                        "reason": "accepted_unparseable_timestamp",
                    }
                )

            days_since = (datetime.now(timezone.utc) - accepted_dt).days
            if days_since >= validity_days:
                return JSONResponse(
                    content={
                        "has_accepted": False,
                        "reason": "expired",
                        "accepted_at": accepted_at,
                        "version": version,
                        "valid_days": validity_days,
                    }
                )

        return JSONResponse(
            content={
                "has_accepted": accepted,
                "accepted_at": accepted_at,
                "version": version,
            }
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error checking T&C")


# ✅ POST — Registrar la aceptación de términos
@router.post("/accept_terms")
async def accept_terms(payload: AcceptTermsPayload, request: Request):
    """
    Registers or updates a client's acceptance of Terms & Conditions.
    Stores timestamp, IP, and User-Agent for audit tracking.
    """
    try:
        authorize_client_request(request, payload.client_id)
        now = datetime.now(timezone.utc).isoformat()

        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "unknown")

        response = (
            supabase.table("client_terms_acceptance")
            .upsert(
                {
                    "client_id": payload.client_id,
                    "accepted": True,
                    "accepted_at": now,
                    "version": "v1",
                    "ip_address": ip,
                    "user_agent": ua,
                },
                on_conflict="client_id",
            )
            .execute()
        )

        if response.data:
            return JSONResponse(
                content={
                    "message": "✅ Terms accepted successfully",
                    "accepted_at": now,
                }
            )

        raise HTTPException(status_code=500, detail="Failed to save acceptance")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error saving T&C acceptance")


# 🔁 GET — Determinar si debe mostrarse el WelcomeModal
@router.get("/should_show_welcome")
def should_show_welcome(request: Request, client_id: str = Query(...)):
    """
    Determines if the WelcomeModal should be shown again.
    The modal is displayed if there is no record or if 30+ days passed since last acceptance.
    """
    try:
        authorize_client_request(request, client_id)
        response = (
            supabase.table("client_terms_acceptance")
            .select("accepted_at, version, accepted")
            .eq("client_id", client_id)
            .order("accepted_at", desc=True)
            .limit(20)
            .execute()
        )

        now = datetime.now(timezone.utc)
        validity_days = _terms_valid_days()

        # 🚀 Sin registro → mostrar modal
        if not response.data or len(response.data) == 0:
            return {"show": True, "reason": "no_record"}

        record = next((r for r in response.data if bool(r.get("accepted"))), response.data[0])
        if not bool(record.get("accepted")):
            return {"show": True, "reason": "not_accepted"}

        accepted_at = record.get("accepted_at")

        # 🚀 Sin fecha → mostrar modal
        if not accepted_at:
            return {"show": True, "reason": "missing_accepted_at"}

        if validity_days <= 0:
            return {"show": False, "reason": "accepted_no_expiry"}

        accepted_dt = _parse_accepted_at(accepted_at)
        if not accepted_dt:
            return {"show": False, "reason": "accepted_unparseable_timestamp"}

        days_since = (now - accepted_dt).days
        if days_since >= validity_days:
            return {"show": True, "reason": "expired", "days_since": days_since, "valid_days": validity_days}
        return {"show": False, "days_remaining": max(0, validity_days - days_since)}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error in should_show_welcome")
