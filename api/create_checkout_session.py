from fastapi import APIRouter, Request
import stripe
import os
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    client_id = data.get("client_id")
    plan_id = data.get("plan_id")
    stripe_price_id = data.get("price_id")

    if not client_id or not plan_id or not stripe_price_id:
        return {"error": "Missing required parameters."}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": stripe_price_id,
                "quantity": 1,
            }],
            mode="subscription",  # usa "payment" si es una compra única
            success_url=os.getenv("STRIPE_SUCCESS_URL", "https://evolvianai.net/success"),
            cancel_url=os.getenv("STRIPE_CANCEL_URL", "https://evolvianai.net/cancel"),
            client_reference_id=client_id,
            metadata={"plan_id": plan_id}
        )

        return {"url": session.url}

    except Exception as e:
        print("❌ Error creando sesión de Stripe:", e)
        return {"error": str(e)}
