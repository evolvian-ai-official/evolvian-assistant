# api/terms_api.py

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from modules.assistant_rag.supabase_client import supabase

# Inicialización del router de FastAPI
router = APIRouter()

# Pydantic model para el payload de aceptación de términos
class AcceptTermsPayload(BaseModel):
    client_id: str

# Ruta GET para verificar si los términos han sido aceptados
@router.get("/accepted_terms")
def check_accepted_terms(client_id: str = Query(...)):
    try:
        # Consulta en la base de datos si el cliente ha aceptado los términos
        response = supabase.table("client_terms_acceptance")\
            .select("client_id")\
            .eq("client_id", client_id)\
            .execute()

        # Verifica si el cliente tiene un registro de aceptación
        accepted = bool(response.data and len(response.data) > 0)

        # Devuelve si el cliente ha aceptado los términos
        return JSONResponse(content={"has_accepted": accepted})

    except Exception as e:
        # Si ocurre un error, se maneja y se lanza una excepción HTTP
        print("❌ Error al verificar T&C:", e)
        raise HTTPException(status_code=500, detail="Error al verificar T&C")

# Ruta POST para registrar la aceptación de términos
@router.post("/accept_terms")
def accept_terms(payload: AcceptTermsPayload):
    try:
        # Obtener la fecha y hora actual
        now = datetime.utcnow().isoformat()

        # Inserta o actualiza el registro de aceptación de términos
        supabase.table("client_terms_acceptance").upsert({
            "client_id": payload.client_id,
            "accepted_at": now,
            "accepted": True
        }, on_conflict="client_id").execute()

        # Respuesta de éxito cuando los términos son aceptados
        return JSONResponse(content={"message": "Términos aceptados"})
    
    except Exception as e:
        # Manejo de errores en caso de fallo al registrar la aceptación
        print("❌ Error al registrar T&C:", e)
        raise HTTPException(status_code=500, detail="Error al registrar T&C")
