# api/client_settings_api.py

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from modules.assistant_rag.supabase_client import supabase

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

router = APIRouter()

# ------------------------------
# POST /client_settings
# ------------------------------

class ClientSettingsPayload(BaseModel):
    client_id: str
    plan: Optional[str] = None  # Puede no venir para evitar sobrescribir
    max_messages: Optional[int] = 100
    assistant_name: Optional[str] = "Evolvian Assistant"
    language: Optional[str] = "es"
    temperature: Optional[float] = 0.7
    show_powered_by: Optional[bool] = True
    custom_prompt: Optional[str] = None
    require_email: Optional[bool] = False
    require_phone: Optional[bool] = False
    require_terms: Optional[bool] = False

@router.post("/client_settings")
def upsert_client_settings(payload: ClientSettingsPayload):
    try:
        payload_dict = {k: v for k, v in payload.dict().items() if v is not None}

        # Verificar si se está enviando plan
        plan_id = payload_dict.get("plan")

        if plan_id:
            plan_check = supabase.table("plans").select("id").eq("id", plan_id).single().execute()
            if not plan_check.data:
                raise HTTPException(status_code=400, detail="Plan no válido")
        else:
            current_plan_res = supabase.table("client_settings")\
                .select("plan")\
                .eq("client_id", payload.client_id)\
                .single()\
                .execute()
            plan_id = current_plan_res.data["plan"] if current_plan_res.data else "free"
            payload_dict.pop("plan", None)  # ✅ No sobrescribimos el plan si no lo mandaron

        # ¿Puede editar custom_prompt?
        allow_custom_prompt = plan_id in ["premium", "white_label"]
        if not allow_custom_prompt:
            payload_dict.pop("custom_prompt", None)

        # Upsert sin sobreescribir plan innecesariamente
        response = supabase.table("client_settings").upsert(payload_dict, on_conflict="client_id").execute()

        if response.data:
            return JSONResponse(content={
                "message": "Configuración guardada correctamente.",
                "settings": response.data[0]
            })
        else:
            raise HTTPException(status_code=500, detail="Error al guardar la configuración.")

    except Exception as e:
        print(f"❌ Error en POST /client_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------
# GET /client_settings?client_id=...
# ------------------------------

@router.get("/client_settings")
def get_client_settings(client_id: str = Query(...)):
    try:
        response = supabase.table("client_settings").select("""
            client_id,
            assistant_name,
            language,
            temperature,
            show_powered_by,
            custom_prompt,
            require_email,
            require_phone,
            require_terms,
            plan:plan(
                id,
                name,
                max_messages,
                max_documents,
                is_unlimited,
                show_powered_by,
                supports_chat,
                supports_email,
                supports_whatsapp,
                price_usd,
                plan_features(feature)
            )
        """).eq("client_id", client_id).single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        settings = response.data

        # ✅ Asegurar booleans correctos
        settings["require_email"] = bool(settings.get("require_email", False))
        settings["require_phone"] = bool(settings.get("require_phone", False))
        settings["require_terms"] = bool(settings.get("require_terms", False))

        # Asegurar que plan_features esté presente como lista
        if "plan" in settings:
            settings["plan"]["plan_features"] = settings["plan"].get("plan_features", [])

        if not settings.get("custom_prompt"):
            settings["custom_prompt"] = DEFAULT_PROMPT

        return JSONResponse(content=settings)

    except Exception as e:
        print(f"❌ Error en GET /client_settings: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener la configuración.")
