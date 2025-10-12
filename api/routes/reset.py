# routes/reset.py
from fastapi import APIRouter
import logging
from api.modules.assistant_rag.supabase_client import supabase





router = APIRouter()

@router.post("/reset_subscriptions")
async def reset_subscriptions():
    """
    Ejecuta la función SQL public.reset_subscription_cycles()
    para resetear los ciclos de suscripción de todos los clientes.
    """
    try:
        query = "select public.reset_subscription_cycles();"
        response = supabase.postgres_execute(query)

        logging.info("✅ reset_subscription_cycles ejecutado con éxito")
        return {"status": "ok", "details": response}
    except Exception as e:
        logging.error(f"❌ Error ejecutando reset_subscription_cycles: {e}")
        return {"status": "error", "message": str(e)}
