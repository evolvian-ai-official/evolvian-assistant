from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from api.modules.assistant_rag.supabase_client import supabase

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

router = APIRouter()

# ------------------------------
# POST /client_settings
# ------------------------------

class ClientSettingsPayload(BaseModel):
    client_id: str
    plan: Optional[str] = None
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

        plan_id = payload_dict.get("plan")

        if plan_id:
            plan_check = supabase.table("plans").select("id").eq("id", plan_id).single().execute()
            if not plan_check.data:
                raise HTTPException(status_code=400, detail="Plan no válido")
        else:
            current_plan_res = supabase.table("client_settings")\
                .select("plan_id")\
                .eq("client_id", payload.client_id)\
                .single()\
                .execute()
            plan_id = current_plan_res.data["plan_id"] if current_plan_res.data else "free"
            payload_dict.pop("plan", None)

        allow_custom_prompt = plan_id in ["premium", "white_label"]
        if not allow_custom_prompt:
            payload_dict.pop("custom_prompt", None)

        if payload.plan:
            payload_dict["plan_id"] = payload.plan
            payload_dict.pop("plan", None)

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
            subscription_id,
            subscription_start,
            subscription_end,
            plan:plan_id(
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

        settings["require_email"] = bool(settings.get("require_email", False))
        settings["require_phone"] = bool(settings.get("require_phone", False))
        settings["require_terms"] = bool(settings.get("require_terms", False))

        if not settings.get("plan") or not settings["plan"].get("id"):
            print("⚠️ Fallback: plan vacío, asignando plan FREE")
            settings["plan"] = {
                "id": "free",
                "name": "Free",
                "max_messages": 100,
                "max_documents": 3,
                "is_unlimited": False,
                "show_powered_by": True,
                "supports_chat": True,
                "supports_email": False,
                "supports_whatsapp": False,
                "price_usd": 0,
                "plan_features": []
            }

        settings["plan"]["plan_features"] = settings["plan"].get("plan_features", [])

        if not settings.get("custom_prompt"):
            settings["custom_prompt"] = DEFAULT_PROMPT

        plans_response = supabase.table("plans").select("""
            id,
            name,
            max_messages,
            max_documents,
            is_unlimited,
            supports_chat,
            supports_email,
            supports_whatsapp,
            show_powered_by,
            price_usd
        """).order("price_usd").execute()

        settings["available_plans"] = plans_response.data if plans_response.data else []

        return JSONResponse(content=settings)

    except Exception as e:
        print(f"❌ Error en GET /client_settings: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener la configuración.")
