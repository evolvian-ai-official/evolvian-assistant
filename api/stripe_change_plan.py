from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from datetime import datetime
from api.config.config import supabase
from api.utils.stripe_plan_utils import modify_subscription_plan, cancel_subscription_at_period_end

import stripe
load_dotenv()

router = APIRouter()

plan_lookup = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "premium": os.getenv("STRIPE_PRICE_PREMIUM"),
    "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL"),
}

@router.post("/change-plan")
async def change_plan(request: Request):
    print("🔄 Recibiendo solicitud para cambiar de plan...")

    try:
        data = await request.json()
        client_id = data.get("client_id")
        new_plan_id = data.get("new_plan_id")

        if not client_id or not new_plan_id:
            raise HTTPException(status_code=400, detail="Faltan parámetros requeridos.")

        print(f"➡️ Cliente {client_id} desea cambiar a plan '{new_plan_id}'")

        # 📦 Obtener plan actual y suscripción
        res = supabase.table("client_settings").select("plan_id, subscription_id")\
            .eq("client_id", client_id).maybe_single().execute()

        if not res or not res.data:
            raise HTTPException(status_code=404, detail="Cliente no encontrado en client_settings")

        current_plan = res.data.get("plan_id")
        subscription_id = res.data.get("subscription_id")
        print(f"🔍 Plan actual: {current_plan} | Sub ID: {subscription_id}")

        if not subscription_id:
            raise HTTPException(status_code=400, detail="Este cliente no tiene una suscripción activa")

        # ⚖️ Evaluar tipo de cambio
        is_upgrade = current_plan == "starter" and new_plan_id == "premium"
        is_downgrade = current_plan == "premium" and new_plan_id == "starter"
        is_to_free = new_plan_id == "free"

        # 👇 Downgrade a plan FREE
        if is_to_free:
            print("⏳ Downgrade a FREE: cancelación al final del ciclo")
            cancel_subscription_at_period_end(subscription_id)

            supabase.table("client_settings").update({
                "plan_id": "free",
                "subscription_id": None,
                "subscription_start": None,
                "subscription_end": None,
                "cancellation_requested_at": datetime.utcnow().isoformat()
            }).eq("client_id", client_id).execute()

            return JSONResponse({"status": "scheduled_cancel", "message": "Suscripción cancelada y plan actualizado a Free"})

        # 👇 Upgrade o downgrade entre planes pagos
        price_id = plan_lookup.get(new_plan_id)
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan inválido")

        print(f"🧠 Cambio detectado: {'upgrade' if is_upgrade else 'downgrade'} ➜ ejecutando modificación...")
        modify_subscription_plan(subscription_id, price_id)

        supabase.table("client_settings").update({
            "plan_id": new_plan_id,
            "cancellation_requested_at": None  # ✅ limpiamos si antes había cancelado
        }).eq("client_id", client_id).execute()

        return JSONResponse({"status": "ok", "message": f"Suscripción actualizada a {new_plan_id}"})

    except Exception as e:
        print("🔥 Error en cambio de plan:", e)
        raise HTTPException(status_code=500, detail=str(e))
