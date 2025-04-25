from fastapi import APIRouter, Query, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class AcceptTermsPayload(BaseModel):
    client_id: str

# ---------------------------
# GET /accepted_terms
# ---------------------------
@router.get("/accepted_terms")
def check_accepted_terms(client_id: str = Query(...)):
    try:
        response = supabase.table("client_terms_acceptance").select("accepted").eq("client_id", client_id).single().execute()
        accepted = response.data["accepted"] if response.data else False
        return JSONResponse(content={"has_accepted": accepted})
    except Exception as e:
        print("❌ Error al verificar T&C:", e)
        return JSONResponse(content={"has_accepted": False})

# ---------------------------
# POST /accept_terms
# ---------------------------
@router.post("/accept_terms")
def accept_terms(payload: AcceptTermsPayload = Body(...)):
    try:
        print(f"📩 Recibiendo aceptación de términos para client_id: {payload.client_id}")
        response = supabase.table("client_terms_acceptance").upsert({
            "client_id": payload.client_id,
            "accepted": True,
            "accepted_at": datetime.utcnow(),
            "version": "v1"
        }, on_conflict="client_id").execute()

        if response.error:
            print("❌ Supabase error:", response.error)
            raise HTTPException(status_code=500, detail="Error al guardar aceptación en Supabase")

        print("✅ Términos aceptados guardados:", response.data)
        return JSONResponse(content={"message": "Términos aceptados"})
    except Exception as e:
        print("❌ Error al aceptar términos:", str(e))
        raise HTTPException(status_code=500, detail="Error al aceptar términos")
