from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from api.modules.assistant_rag.supabase_client import supabase

# ✅ Inicialización del router
router = APIRouter()

# 📦 Modelo para payload de aceptación
class AcceptTermsPayload(BaseModel):
    client_id: str


# 🧭 GET — Verificar si el cliente ya aceptó los términos
@router.get("/accepted_terms")
def check_accepted_terms(client_id: str = Query(...)):
    """
    Checks if the client has accepted the Terms & Conditions.
    Returns acceptance status, date, and version.
    """
    try:
        response = (
            supabase.table("client_terms_acceptance")
            .select("client_id, accepted_at, version, accepted")
            .eq("client_id", client_id)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            return JSONResponse(content={"has_accepted": False})

        record = response.data[0]
        return JSONResponse(
            content={
                "has_accepted": bool(record.get("accepted")),
                "accepted_at": record.get("accepted_at"),
                "version": record.get("version", "v1"),
            }
        )

    except Exception as e:
        print("❌ Error checking T&C:", e)
        raise HTTPException(status_code=500, detail="Error checking T&C")


# ✅ POST — Registrar la aceptación de términos
@router.post("/accept_terms")
def accept_terms(payload: AcceptTermsPayload):
    """
    Registers or updates a client's acceptance of Terms & Conditions.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()

        response = (
            supabase.table("client_terms_acceptance")
            .upsert(
                {
                    "client_id": payload.client_id,
                    "accepted": True,
                    "accepted_at": now,
                    "version": "v1",
                },
                on_conflict="client_id",
            )
            .execute()
        )

        if response.data:
            return JSONResponse(content={"message": "✅ Terms accepted successfully", "updated_at": now})
        else:
            raise HTTPException(status_code=500, detail="Failed to register terms acceptance")

    except Exception as e:
        print("❌ Error in /accept_terms:", e)
        raise HTTPException(status_code=500, detail="Error saving T&C acceptance")


# 🔁 GET — Controlar si debe mostrarse el WelcomeModal cada mes
@router.get("/should_show_welcome")
def should_show_welcome(client_id: str = Query(...)):
    """
    Determines if the WelcomeModal should be shown again.
    It is displayed every 30 days (1 month) since last acceptance.
    Uses client_terms_acceptance.accepted_at as reference.
    """
    try:
        response = (
            supabase.table("client_terms_acceptance")
            .select("accepted_at, version")
            .eq("client_id", client_id)
            .execute()
        )

        now = datetime.now(timezone.utc)

        # 🚀 No hay registro → mostrar modal
        if not response.data or len(response.data) == 0:
            return {"show": True, "reason": "No acceptance record found"}

        record = response.data[0]
        accepted_at = record.get("accepted_at")

        # 🚀 Registro sin fecha → mostrar modal
        if not accepted_at:
            return {"show": True, "reason": "Missing accepted_at"}

        # 📆 Calcular días transcurridos
        accepted_dt = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
        days_since = (now - accepted_dt).days

        if days_since >= 30:
            # Mostrar modal si han pasado 30 días o más
            return {"show": True, "reason": f"{days_since} days since last acceptance"}
        else:
            # No mostrar si aún no ha pasado el mes
            return {"show": False, "days_remaining": 30 - days_since}

    except Exception as e:
        print("🔥 Error in should_show_welcome:", e)
        return {"show": True, "error": str(e)}
