# api/terms_api.py
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from api.modules.assistant_rag.supabase_client import supabase  # ✅ import corregido
from api.authz import authorize_client_request

router = APIRouter()

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
            .execute()
        )

        # 🚫 No hay registro → nunca aceptó
        if not response.data or len(response.data) == 0:
            return JSONResponse(content={"has_accepted": False, "reason": "not_found"})

        record = response.data[0]
        accepted = bool(record.get("accepted"))
        accepted_at = record.get("accepted_at")
        version = record.get("version", "v1")

        # ⚙️ Si aceptó, verificar vigencia (30 días)
        if accepted and accepted_at:
            try:
                accepted_dt = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - accepted_dt).days

                if days_since >= 30:
                    return JSONResponse(
                        content={
                            "has_accepted": False,
                            "reason": "expired",
                            "accepted_at": accepted_at,
                            "version": version,
                        }
                    )
            except Exception:
                return JSONResponse(
                    content={
                        "has_accepted": False,
                        "reason": "invalid_timestamp",
                        "version": version,
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
            .select("accepted_at, version")
            .eq("client_id", client_id)
            .execute()
        )

        now = datetime.now(timezone.utc)

        # 🚀 Sin registro → mostrar modal
        if not response.data or len(response.data) == 0:
            return {"show": True, "reason": "no_record"}

        record = response.data[0]
        accepted_at = record.get("accepted_at")

        # 🚀 Sin fecha → mostrar modal
        if not accepted_at:
            return {"show": True, "reason": "missing_accepted_at"}

        accepted_dt = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
        days_since = (now - accepted_dt).days

        if days_since >= 30:
            return {"show": True, "reason": "expired", "days_since": days_since}
        else:
            return {"show": False, "days_remaining": 30 - days_since}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error in should_show_welcome")
