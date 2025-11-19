from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

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
    print("📦 Payload recibido en /register_consent:", data.dict())

    try:
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
            "consent_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": request.client.host,
            "user_agent": data.user_agent or request.headers.get("user-agent"),
        }

        print("🧾 Payload final a insertar:", payload)

        # 💾 Insertar (o upsert opcional)
        result = supabase.table("widget_consents").insert(payload).execute()

        if not result or not result.data:
            print("❌ Error Supabase insert:", result.error if result else "sin respuesta")
            raise HTTPException(status_code=500, detail="Failed to register consent")

        print("✅ Consentimiento registrado correctamente:", result.data)
        return {"message": "Consent registered successfully", "client_id": client_id}

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"❌ Error en /register_consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
