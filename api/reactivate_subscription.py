from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
import stripe
import os

router = APIRouter()

STRIPE_API_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


@router.post("/reactivate-subscription")
async def reactivate_subscription(request: Request):
    """
    Reactiva una suscripción pendiente de cancelación.
    Limpia cancellation_requested_at y scheduled_plan_id en Supabase.
    Si es una suscripción simulada (sub_test_), no llama a Stripe.
    """
    try:
        body = await request.json()
        client_id = body.get("client_id")

        if not client_id:
            raise HTTPException(status_code=400, detail="Missing client_id")

        # 🔹 Buscar configuración del cliente
        settings_res = (
            supabase.table("client_settings")
            .select("subscription_id, cancellation_requested_at, scheduled_plan_id")
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        if not settings_res.data:
            raise HTTPException(status_code=404, detail="No client settings found")

        subscription_id = settings_res.data.get("subscription_id")
        cancel_flag = settings_res.data.get("cancellation_requested_at")

        if not subscription_id:
            raise HTTPException(status_code=404, detail="No subscription found for this client")

        if not cancel_flag:
            return JSONResponse(content={"message": "No pending cancellation to reactivate."})

        # 🔹 Si es una suscripción simulada (sin Stripe real)
        if subscription_id.startswith("sub_test_"):
            print(f"🧪 Reactivando suscripción simulada para cliente {client_id}")
            supabase.table("client_settings").update({
                "cancellation_requested_at": None,
                "scheduled_plan_id": None
            }).eq("client_id", client_id).execute()
            return JSONResponse(content={"message": "Test subscription reactivated locally."})

        # 🔹 Reactivar en Stripe real
        try:
            stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        except Exception as e:
            print(f"⚠️ Stripe modify error: {e}")
            raise HTTPException(status_code=500, detail=f"Stripe reactivation failed: {str(e)}")

        # 🔹 Limpiar banderas en Supabase
        update_res = (
            supabase.table("client_settings")
            .update({
                "cancellation_requested_at": None,
                "scheduled_plan_id": None
            })
            .eq("client_id", client_id)
            .execute()
        )

        if update_res.error:
            print(f"❌ Supabase update error: {update_res.error}")
            raise HTTPException(status_code=500, detail="Failed to update Supabase")

        print(f"✅ Subscription reactivated for client {client_id}")
        return JSONResponse(content={"message": "Subscription successfully reactivated."})

    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

    except Exception as e:
        print(f"❌ Error en /reactivate-subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))
