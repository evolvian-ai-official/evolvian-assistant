from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging
from api.modules.assistant_rag.supabase_client import supabase
from api.security.request_limiter import enforce_rate_limit, get_request_ip
from api.authz import authorize_client_request

router = APIRouter()
logger = logging.getLogger(__name__)

# ===============================================
# 📋 Modelo de entrada (corregido)
# ===============================================
class ConsentInput(BaseModel):
    public_client_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    accepted_terms: Optional[bool] = False
    accepted_email_marketing: Optional[bool] = False
    user_agent: Optional[str] = None


class ClientConsentInput(BaseModel):
    client_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    accepted_terms: Optional[bool] = False
    accepted_email_marketing: Optional[bool] = False
    user_agent: Optional[str] = None
    consent_at: Optional[datetime] = None


# ===============================================
# 🧾 Endpoint principal
# ===============================================
@router.post("/register_consent")
async def register_consent(data: ConsentInput, request: Request):
    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="register_consent_ip",
            key=f"{data.public_client_id}:{request_ip}",
            limit=30,
            window_seconds=60,
        )

        # 🧠 Buscar el cliente por public_client_id
        client_res = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", data.public_client_id)
            .execute()
        )

        if not client_res or not client_res.data:
            raise HTTPException(status_code=404, detail="Client not found")

        client_id = client_res.data[0]["id"]

        # 🧹 Sanitizar email/phone
        email_value = data.email.strip() if data.email and data.email.strip() != "" else None
        phone_value = data.phone.strip() if data.phone and data.phone.strip() != "" else None

        # 🧾 Construir payload (identación fija + timestamp válido)
        payload = {
            "client_id": client_id,
            "email": email_value,
            "phone": phone_value,
            "accepted_terms": bool(data.accepted_terms),
            "accepted_email_marketing": bool(data.accepted_email_marketing),
            "consent_at": datetime.utcnow().isoformat(),
            "ip_address": request.client.host if request.client else None,
            "user_agent": data.user_agent or request.headers.get("user-agent"),
        }

        # 💾 Insertar (o upsert opcional)
        result = supabase.table("widget_consents").insert(payload).execute()

        if not result or not result.data:
            raise HTTPException(status_code=500, detail="Failed to register consent")

        consent_row = result.data[0] if isinstance(result.data, list) and result.data else {}
        return {
            "message": "Consent registered successfully",
            "client_id": client_id,
            "consent_token": consent_row.get("id"),
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en /register_consent")
        raise HTTPException(status_code=500, detail="Failed to register consent")


@router.post("/register_client_consent")
async def register_client_consent(data: ClientConsentInput, request: Request):
    """
    Authenticated consent registration for non-widget flows.
    Useful when consent is collected externally (CRM/call center/forms).
    """
    try:
        if not data.client_id:
            raise HTTPException(status_code=400, detail="client_id is required")
        authorize_client_request(request, data.client_id)

        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="register_client_consent_ip",
            key=f"{data.client_id}:{request_ip}",
            limit=60,
            window_seconds=60,
        )

        email_value = data.email.strip().lower() if data.email and data.email.strip() else None
        phone_value = data.phone.strip() if data.phone and data.phone.strip() else None
        if not email_value and not phone_value:
            raise HTTPException(status_code=422, detail="email or phone is required")

        consent_at = data.consent_at
        if consent_at is None:
            consent_at = datetime.now(timezone.utc)
        elif consent_at.tzinfo is None:
            consent_at = consent_at.replace(tzinfo=timezone.utc)
        else:
            consent_at = consent_at.astimezone(timezone.utc)

        payload = {
            "client_id": data.client_id,
            "email": email_value,
            "phone": phone_value,
            "accepted_terms": bool(data.accepted_terms),
            "accepted_email_marketing": bool(data.accepted_email_marketing),
            "consent_at": consent_at.isoformat(),
            "ip_address": request_ip,
            "user_agent": data.user_agent or request.headers.get("user-agent"),
        }
        result = supabase.table("widget_consents").insert(payload).execute()
        if not result or not result.data:
            raise HTTPException(status_code=500, detail="Failed to register client consent")

        consent_row = result.data[0] if isinstance(result.data, list) and result.data else {}
        return {
            "message": "Client consent registered successfully",
            "client_id": data.client_id,
            "consent_token": consent_row.get("id"),
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en /register_client_consent")
        raise HTTPException(status_code=500, detail="Failed to register client consent")
