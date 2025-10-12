from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import supabase
from api.utils.stripe_plan_utils import cancel_subscription_immediately_if_exists

load_dotenv()
router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    print("📥 Recibiendo petición para crear checkout session...")

    try:
        data = await request.json()
    except Exception as e:
        print("❌ Error al parsear JSON:", e)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    plan_id = data.get("plan_id")
    client_id = data.get("client_id")

    if not plan_id or not client_id:
        print("⚠️ Falta plan_id o client_id")
        raise HTTPException(status_code=400, detail="Missing plan_id or client_id")

    print(f"🔎 Creando sesión para plan '{plan_id}' y cliente '{client_id}'")

    plan_lookup = {
        "starter": os.getenv("STRIPE_PRICE_STARTER"),
        "premium": os.getenv("STRIPE_PRICE_PREMIUM"),
        "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL")
    }

    price_id = plan_lookup.get(plan_id)
    if not price_id:
        print("❌ plan_id inválido:", plan_id)
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    # Determinar URLs de redirección según entorno
    env = os.getenv("ENV", "prod")
    success_url = (
        "http://localhost:5173/dashboard"
        if env == "local"
        else os.getenv("STRIPE_SUCCESS_URL", "https://www.evolvianai.net/settings")
    )
    cancel_url = (
        "http://localhost:5173/settings"
        if env == "local"
        else os.getenv("STRIPE_CANCEL_URL", "https://www.evolvianai.net/settings")
    )

    try:
        # 🔍 Buscar suscripción activa del cliente
        active = supabase.table("client_settings")\
            .select("subscription_id")\
            .eq("client_id", client_id)\
            .maybe_single()\
            .execute()

        subscription_id = active.data.get("subscription_id") if active and active.data else None

        # 🧹 Cancelar suscripción anterior si existe
        if subscription_id:
            await cancel_subscription_immediately_if_exists(subscription_id)

        # 🧾 Crear nueva sesión de Stripe
        print("🚀 Creando nueva sesión de checkout en Stripe...")
        session = stripe.checkout.Session.create(
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=client_id,
            metadata={"plan_id": plan_id}
        )

        print("✅ Sesión creada:", session.url)
        return JSONResponse({"url": session.url})

    except Exception as e:
        print("🔥 Error al crear sesión en Stripe:", e)
        raise HTTPException(status_code=500, detail="Stripe error: " + str(e))
