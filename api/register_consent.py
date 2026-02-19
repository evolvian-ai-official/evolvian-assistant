from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
from api.modules.assistant_rag.supabase_client import supabase
from api.security.request_limiter import enforce_rate_limit, get_request_ip

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
