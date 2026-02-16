# routes/reset.py
from fastapi import APIRouter, HTTPException, Request
import logging
import os
from api.modules.assistant_rag.supabase_client import supabase





router = APIRouter()

@router.post("/reset_subscriptions")
async def reset_subscriptions(request: Request):
    """
    Ejecuta la función SQL public.reset_subscription_cycles()
    para resetear los ciclos de suscripción de todos los clientes.
    """
    try:
        admin_token = os.getenv("RESET_SUBSCRIPTIONS_TOKEN")
        provided_token = request.headers.get("x-reset-token")

        if not admin_token:
            logging.error("❌ RESET_SUBSCRIPTIONS_TOKEN no está configurado.")
            raise HTTPException(status_code=503, detail="reset_subscriptions_not_configured")

        if provided_token != admin_token:
            logging.warning("🚫 Intento no autorizado de /reset_subscriptions.")
            raise HTTPException(status_code=403, detail="forbidden")

        query = "select public.reset_subscription_cycles();"
        response = supabase.postgres_execute(query)

        logging.info("✅ reset_subscription_cycles ejecutado con éxito")
        return {"status": "ok", "details": response}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Error ejecutando reset_subscription_cycles: {e}")
        return {"status": "error", "message": str(e)}
