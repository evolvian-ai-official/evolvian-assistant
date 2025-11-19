# ============================================================
# 📅 api/calendar_settings.py
# ------------------------------------------------------------
# Controla la configuración del calendario por cliente.
# Usa "calendar_status" en lugar de boolean para evitar conflictos.
# ============================================================

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase
import logging

router = APIRouter(tags=["Calendar Settings"])
logger = logging.getLogger("calendar_settings")

# ============================================================
# 📦 Pydantic Model
# ============================================================
class CalendarSettingsPayload(BaseModel):
    client_id: str
    calendar_status: str = Field(default="inactive", pattern="^(active|inactive)$")
    selected_days: List[str] = Field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"])
    start_time: str = "09:00"
    end_time: str = "18:00"
    slot_duration_minutes: int = 30
    min_notice_hours: int = 4
    max_days_ahead: int = 14
    buffer_minutes: int = 15
    allow_same_day: bool = True
    timezone: str = "America/Mexico_City"


# ============================================================
# 📘 GET /calendar/settings
# ============================================================
@router.get("/calendar/settings")
def get_calendar_settings(client_id: str = Query(...)):
    """
    Devuelve las configuraciones de calendario del cliente.
    """
    try:
        res = (
            supabase.table("calendar_settings")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if res.data:
            return JSONResponse(content=res.data[0])

        return JSONResponse(
            content=CalendarSettingsPayload(client_id=client_id).model_dump()
        )

    except Exception as e:
        logger.exception("❌ Error fetching calendar settings")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 💾 POST /calendar/settings
# ============================================================
@router.post("/calendar/settings")
def upsert_calendar_settings(payload: CalendarSettingsPayload):
    """
    Guarda o actualiza las configuraciones del calendario.
    Usa 'calendar_status' en lugar de boolean para estado.
    """
    try:
        data = payload.model_dump()
        client_id = data.pop("client_id")
        data["updated_at"] = datetime.utcnow().isoformat()

        # Validar el valor del status
        if data["calendar_status"] not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Invalid calendar_status value")

        # Verificar si ya existe registro
        existing = (
            supabase.table("calendar_settings")
            .select("client_id")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            res = (
                supabase.table("calendar_settings")
                .update(data)
                .eq("client_id", client_id)
                .execute()
            )
            logger.info(f"🔄 Updated calendar_status={data['calendar_status']} for {client_id}")
        else:
            res = (
                supabase.table("calendar_settings")
                .insert({"client_id": client_id, **data})
                .execute()
            )
            logger.info(f"🆕 Created new settings with calendar_status={data['calendar_status']}")

        # Confirmar guardado
        confirm = (
            supabase.table("calendar_settings")
            .select("client_id, calendar_status, updated_at")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        saved = confirm.data[0] if confirm.data else {"client_id": client_id, **data}
        logger.info(f"✅ Persisted calendar_status={saved.get('calendar_status')}")
        return JSONResponse(content={"success": True, "settings": saved})

    except Exception as e:
        logger.exception("❌ Error saving calendar settings")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 🧪 PATCH /calendar/status (toggle rápido)
# ============================================================
@router.patch("/calendar/status")
def toggle_calendar_status(client_id: str = Query(...), status: str = Query(...)):
    """
    Permite activar o desactivar el calendario rápidamente desde el frontend.
    """
    try:
        if status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Invalid status value")

        res = (
            supabase.table("calendar_settings")
            .update({"calendar_status": status, "updated_at": datetime.utcnow().isoformat()})
            .eq("client_id", client_id)
            .execute()
        )

        logger.info(f"🔘 Calendar status changed to {status} for {client_id}")
        return JSONResponse(content={"success": True, "calendar_status": status})

    except Exception as e:
        logger.exception("❌ Error toggling calendar status")
        raise HTTPException(status_code=500, detail=str(e))
