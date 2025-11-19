import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase

# ============================================================
# 📘 Router: Estado de integración Google Calendar (para UI)
# ============================================================
router = APIRouter(tags=["Calendar UI Status"])
logger = logging.getLogger("calendar_ui_status")

@router.get("/api/auth/google_calendar")
async def check_google_calendar_connection(client_id: str = Query(...)):
    """
    ✅ Verifica si el cliente tiene una integración activa con Google Calendar.
    Este endpoint es usado exclusivamente por la interfaz de usuario del panel Evolvian.
    """
    try:
        res = (
            supabase.table("calendar_integrations")
            .select("connected_email, calendar_id, is_active")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        # 🟡 No existe integración activa
        if not res or not res.data:
            logger.info(f"ℹ️ No active Google Calendar connection for client {client_id}")
            return JSONResponse(content={"connected": False, "is_active": False})

        record = res.data[0]
        connected_email = record.get("connected_email") or record.get("calendar_id")

        # ✅ Retorna respuesta esperada por el frontend
        logger.info(f"✅ Active Google Calendar connection for {connected_email or 'unknown'}")
        return JSONResponse(
            content={
                "connected": True,
                "is_active": record.get("is_active", False),
                "connected_email": connected_email,
            }
        )

    except Exception as e:
        logger.exception(f"❌ Error verifying Google Calendar connection for {client_id}: {e}")
        return JSONResponse(
            content={"connected": False, "error": str(e)}, status_code=500
        )
