from fastapi import APIRouter, HTTPException, Request
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import update_client_plan_by_id

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
    except Exception as e:
        print("🔥 Error general:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
