# api/check_email_exists.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import requests
import os

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ADMIN_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

class EmailCheckRequest(BaseModel):
    email: str

@router.post("/check_email_exists")
def check_email_exists(payload: EmailCheckRequest):
    try:
        url = f"{SUPABASE_URL}/auth/v1/admin/users"
        headers = {
            "apikey": SUPABASE_ADMIN_KEY,
            "Authorization": f"Bearer {SUPABASE_ADMIN_KEY}"
        }

        print("🔍 Supabase Admin Email Check")
        print("🔗 URL:", url)
        print("🧾 Headers:", headers)

        response = requests.get(url, headers=headers)
        print("📥 Status Code:", response.status_code)
        print("📄 Response Text:", response.text)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error al consultar Supabase")

        users = response.json().get("users", [])

        # Buscar el correo exacto entre los resultados
        match = next((u for u in users if u.get("email") == payload.email), None)

        if match:
            provider = match.get("app_metadata", {}).get("provider", "email")
            return JSONResponse(content={ "exists": True, "provider": provider })
        else:
            return JSONResponse(content={ "exists": False })

    except Exception as e:
        print(f"❌ Error en /check_email_exists: {e}")
        raise HTTPException(status_code=500, detail="No se pudo validar el correo.")
