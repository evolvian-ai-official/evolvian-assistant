from fastapi import APIRouter, HTTPException, Request
import stripe
import os
from dotenv import load_dotenv
from api.authz import authorize_client_request
from api.config.config import supabase
from api.utils.effective_plan import get_client_override_plan_id

load_dotenv()
router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/api/cancel-subscription")
async def cancel_subscription(request: Request):
    try:
        data = await request.json()
        subscription_id = data.get("subscription_id")
        client_id = data.get("client_id")

        if not subscription_id or not client_id:
            raise HTTPException(status_code=400, detail="Missing parameters")
        authorize_client_request(request, client_id)
        override_plan_id = get_client_override_plan_id(client_id, supabase_client=supabase)
        if override_plan_id:
            raise HTTPException(
                status_code=409,
                detail="Plan managed internally for this client; Stripe cancellation is disabled.",
            )

        # ✅ Cancelar al final del período
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True,
        )
        print(f"📅 Suscripción programada para cancelación al final del período: {subscription_id}")

        # 🧠 No bajamos el plan a free aún. Eso lo hace el webhook.
        return {"status": "ok", "message": "Subscription will be cancelled at the end of the billing period"}

    except stripe.error.StripeError as e:
        print("❌ Error de Stripe:", str(e))
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print("🔥 Error general:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
