from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from api.modules.assistant_rag.supabase_client import supabase

# 🧠 Prompt base por defecto
DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

# 🎨 Fuentes permitidas (Google Fonts seguras)
ALLOWED_FONTS = ["Inter", "Roboto", "Poppins", "Open Sans"]

router = APIRouter()

# ------------------------------
# MODELO DE PAYLOAD
# ------------------------------

class ClientSettingsPayload(BaseModel):
    client_id: str
    plan_id: Optional[str] = None
    assistant_name: Optional[str] = "Evolvian Assistant"
    language: Optional[str] = "es"
    temperature: Optional[float] = 0.7
    custom_prompt: Optional[str] = None

    show_powered_by: Optional[bool] = True
    show_logo: Optional[bool] = None
    require_email: Optional[bool] = False
    require_phone: Optional[bool] = False
    require_terms: Optional[bool] = False
    session_message_limit: Optional[int] = 24

    # 🎨 Apariencia visual del widget
    header_color: Optional[str] = None
    header_text_color: Optional[str] = None
    background_color: Optional[str] = None
    user_message_color: Optional[str] = None
    bot_message_color: Optional[str] = None
    button_color: Optional[str] = None
    button_text_color: Optional[str] = None
    footer_text_color: Optional[str] = None
    font_family: Optional[str] = None
    widget_height: Optional[int] = None
    widget_border_radius: Optional[int] = None

    # 📆 Subscripción
    daily_message_limit: Optional[int] = None
    subscription_id: Optional[str] = None
    subscription_start: Optional[str] = None
    subscription_end: Optional[str] = None
    cancellation_requested_at: Optional[str] = None
    subscription_cycles: Optional[int] = None

    class Config:
        extra = "allow"  # ✅ Permite campos adicionales sin fallar


# ------------------------------
# POST /client_settings
# ------------------------------

@router.post("/client_settings")
async def upsert_client_settings(request: Request):
    """Crea o actualiza la configuración del cliente (compatible con plan_id)."""
    try:
        raw = await request.json()
        print("📩 Body recibido (raw):", raw)

        # ⚠️ Validar client_id presente
        if not raw.get("client_id"):
            print("⚠️ Error: Falta client_id en el payload recibido.")
            raise HTTPException(status_code=400, detail="El campo 'client_id' es obligatorio.")

        # 🧹 Normalizar tipos (true/false como booleanos, números como int)
        for k, v in list(raw.items()):
            if isinstance(v, str):
                if v.lower() in ["true", "false"]:
                    raw[k] = v.lower() == "true"
                else:
                    try:
                        if "." in v:
                            raw[k] = float(v)
                        elif v.isdigit():
                            raw[k] = int(v)
                    except ValueError:
                        pass

        # 🩹 Si viene plan como objeto, convertir a plan_id
        if isinstance(raw.get("plan"), dict) and "id" in raw["plan"]:
            raw["plan_id"] = raw["plan"]["id"]
            raw.pop("plan", None)

        # 🎨 Limpieza y validación del campo font_family
        if "font_family" in raw and raw["font_family"]:
            raw["font_family"] = raw["font_family"].replace("'", "").replace('"', "").strip()
            font_name = raw["font_family"].split(",")[0].strip()
            if font_name not in ALLOWED_FONTS:
                print(f"⚠️ Fuente no permitida: {font_name}, usando Inter.")
                raw["font_family"] = "Inter, sans-serif"

        # 🧹 Eliminar campos no existentes en la tabla client_settings
        forbidden_keys = [
            "available_plans", "plan", "plan_features",
            "id", "idx", "created_at", "updated_at",
            "max_messages", "max_documents", "supports_chat",
            "supports_email", "supports_whatsapp"
        ]
        for key in forbidden_keys:
            raw.pop(key, None)

        # ✅ Validar y construir el payload Pydantic
        try:
            payload = ClientSettingsPayload(**raw)
        except Exception as e:
            print(f"❌ Error al validar el payload con Pydantic: {e}")
            raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")

        payload_dict = {k: v for k, v in payload.dict().items() if v is not None}

        # 🔹 Verificar plan válido
        plan_id = payload_dict.get("plan_id")
        if plan_id:
            plan_check = supabase.table("plans").select("id").eq("id", plan_id).single().execute()
            if not plan_check.data:
                raise HTTPException(status_code=400, detail="Plan no válido")
        else:
            current_plan_res = (
                supabase.table("client_settings")
                .select("plan_id")
                .eq("client_id", payload.client_id)
                .maybe_single()
                .execute()
            )
            plan_id = current_plan_res.data["plan_id"] if current_plan_res.data else "free"

        # 🔒 Solo premium / white_label puede editar custom_prompt
        if plan_id not in ["premium", "white_label"]:
            payload_dict.pop("custom_prompt", None)

        # 💾 Guardar configuración limpia
        print("💾 Guardando configuración limpia:", payload_dict)
        response = supabase.table("client_settings").upsert(payload_dict, on_conflict="client_id").execute()

        if response.data:
            print("✅ Configuración guardada correctamente para client_id:", payload.client_id)
            return JSONResponse(
                content={"message": "Configuración guardada correctamente.", "settings": response.data[0]}
            )

        raise HTTPException(status_code=500, detail="Error al guardar la configuración.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en POST /client_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------
# GET /client_settings
# ------------------------------

@router.get("/client_settings")
def get_client_settings(
    client_id: Optional[str] = Query(None),
    public_client_id: Optional[str] = Query(None)
):
    """Obtiene la configuración del cliente."""
    try:
        if not client_id and not public_client_id:
            raise HTTPException(status_code=400, detail="Debe especificarse client_id o public_client_id")

        # Buscar client_id si llega public_client_id
        if public_client_id and not client_id:
            lookup = (
                supabase.table("clients")
                .select("id")
                .eq("public_client_id", public_client_id)
                .single()
                .execute()
            )
            if not lookup.data:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")
            client_id = lookup.data["id"]

        # Obtener settings
        response = (
            supabase.table("client_settings")
            .select("""
                client_id,
                assistant_name,
                language,
                temperature,
                show_powered_by,
                show_logo,
                custom_prompt,
                daily_message_limit,
                require_email,
                require_phone,
                require_terms,
                plan_id,
                subscription_id,
                subscription_start,
                subscription_end,
                cancellation_requested_at,
                subscription_cycles,
                created_at,
                header_color,
                header_text_color,
                background_color,
                user_message_color,
                bot_message_color,
                button_color,
                button_text_color,
                footer_text_color,
                font_family,
                widget_height,
                widget_border_radius,
                session_message_limit,
                plan:plan_id(
                    id,
                    name,
                    description,
                    max_messages,
                    max_documents,
                    is_unlimited,
                    show_powered_by,
                    supports_chat,
                    supports_email,
                    supports_whatsapp,
                    price_usd,
                    duration,
                    plan_features(feature)
                )
            """)
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        settings = response.data

        # Normalizar booleanos
        for key in ["require_email", "require_phone", "require_terms", "show_powered_by", "show_logo"]:
            settings[key] = bool(settings.get(key, key != "show_powered_by"))

        # Fallback de plan
        plan = settings.get("plan", {})
        if not plan or not plan.get("id"):
            plan = {
                "id": "free",
                "name": "Free",
                "max_messages": 100,
                "max_documents": 3,
                "supports_chat": True,
                "supports_email": False,
                "supports_whatsapp": False,
                "price_usd": 0,
                "plan_features": []
            }
        settings["plan"] = plan

        # Fallback de prompt
        if not settings.get("custom_prompt"):
            settings["custom_prompt"] = DEFAULT_PROMPT

        # 🎨 Fallback de fuente
        font_raw = settings.get("font_family", "")
        if not font_raw or font_raw.strip() == "":
            font_raw = "Inter, sans-serif"
        else:
            font_raw = font_raw.replace("'", "").replace('"', "").strip()
            font_name = font_raw.split(",")[0].strip()
            if font_name not in ALLOWED_FONTS:
                print(f"⚠️ Fuente desconocida ({font_name}), usando Inter por defecto.")
                font_raw = "Inter, sans-serif"

        settings["font_family"] = font_raw

        # Si plan no es premium/white_label, aplicar tema base
        plan_id = plan["id"]
        if plan_id not in ["premium", "white_label"]:
            settings.update({
                "header_color": settings.get("header_color") or "#fff9f0",
                "header_text_color": settings.get("header_text_color") or "#1b2a41",
                "background_color": settings.get("background_color") or "#ffffff",
                "user_message_color": settings.get("user_message_color") or "#a3d9b1",
                "bot_message_color": settings.get("bot_message_color") or "#f7f7f7",
                "button_color": settings.get("button_color") or "#f5a623",
                "button_text_color": settings.get("button_text_color") or "#ffffff",
                "footer_text_color": settings.get("footer_text_color") or "#999999",
                "widget_height": settings.get("widget_height") or 420,
                "widget_border_radius": settings.get("widget_border_radius") or 13,
                "show_logo": settings.get("show_logo", True),
            })

        # Listar planes disponibles
        plans_response = (
            supabase.table("plans")
            .select("""
                id, name, description, max_messages, max_documents,
                is_unlimited, supports_chat, supports_email, supports_whatsapp,
                show_powered_by, price_usd, duration
            """)
            .order("price_usd")
            .execute()
        )
        settings["available_plans"] = plans_response.data or []

        return JSONResponse(content=settings)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en GET /client_settings: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener configuración: {str(e)}")
