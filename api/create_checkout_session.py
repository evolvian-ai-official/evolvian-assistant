# api/routes/create_checkout_session.py
from fastapi import APIRouter, Request, HTTPException
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
import traceback
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
print(f"🔐 Stripe API Key (inicio): {stripe.api_key[:10] if stripe.api_key else '❌ NOT SET'}...")


def _ensure_success_url_has_session_id(url: str) -> str:
    """
    Stripe no agrega session_id automáticamente si la URL no contiene
    {CHECKOUT_SESSION_ID}. Este helper fuerza esa query param.
    """
    if "{CHECKOUT_SESSION_ID}" in url:
        return url

    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_params["session_id"] = "{CHECKOUT_SESSION_ID}"
    rebuilt_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=rebuilt_query))


@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    client_id = data.get("client_id")
    plan_id = str(data.get("plan_id") or "").strip().lower()
    stripe_price_id = data.get("price_id")  # no confiable desde cliente
    email = data.get("email")

    print("📥 Recibiendo petición para crear checkout session...")
    print(f"🧾 Datos recibidos: client_id={client_id}, plan_id={plan_id}, price_id={stripe_price_id}, email={email}")

    # ✅ Lookup de precios sólo desde backend (fuente de verdad)
    plan_lookup = {
        "starter": os.getenv("STRIPE_PRICE_STARTER_ID"),
        "premium": os.getenv("STRIPE_PRICE_PREMIUM_ID"),
        "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL_ID")
    }
    expected_price_id = plan_lookup.get(plan_id)

    # 🔍 Debug seguro (sin exponer secretos ni valores completos)
    print("──────────────────────── DEBUG STRIPE (SAFE) ─────────────────────")
    print(f"STRIPE_SECRET_KEY configured: {'yes' if os.getenv('STRIPE_SECRET_KEY') else 'no'}")
    print(f"STRIPE_PRICE_STARTER_ID configured: {'yes' if os.getenv('STRIPE_PRICE_STARTER_ID') else 'no'}")
    print(f"STRIPE_PRICE_PREMIUM_ID configured: {'yes' if os.getenv('STRIPE_PRICE_PREMIUM_ID') else 'no'}")
    print(f"stripe_price_id provided: {'yes' if stripe_price_id else 'no'}")
    print(f"stripe.api_key configured in memory: {'yes' if stripe.api_key else 'no'}")
    print(f"STRIPE_SUCCESS_URL configured: {'yes' if os.getenv('STRIPE_SUCCESS_URL') else 'no'}")
    print(f"STRIPE_CANCEL_URL configured: {'yes' if os.getenv('STRIPE_CANCEL_URL') else 'no'}")
    print("──────────────────────────────────────────────────────────────────")

    # Validación final (estricta)
    if not client_id or not plan_id:
        print("⚠️ Faltan parámetros obligatorios para crear la sesión de checkout.")
        raise HTTPException(status_code=400, detail="Missing required parameters.")
    if plan_id not in plan_lookup:
        print(f"⚠️ plan_id inválido recibido: {plan_id}")
        raise HTTPException(status_code=400, detail="Invalid plan_id.")
    if not expected_price_id:
        print(f"⚠️ Falta configuración Stripe price para plan '{plan_id}'.")
        raise HTTPException(status_code=500, detail="Plan price not configured.")
    if stripe_price_id and stripe_price_id != expected_price_id:
        print(
            f"🚫 price_id rechazado. plan_id={plan_id} expected={expected_price_id} provided={stripe_price_id}"
        )
        raise HTTPException(status_code=400, detail="Invalid price_id for selected plan.")

    stripe_price_id = expected_price_id
    authorize_client_request(request, client_id)

    try:
        print(f"🔎 Creando sesión para plan '{plan_id}' y cliente '{client_id}'")

        # -------------------------------------------------------------
        # 1️⃣ Obtener la suscripción anterior (si existe)
        # -------------------------------------------------------------
        current = (
            supabase.table("client_settings")
            .select("subscription_id")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        old_sub = None
        if current and current.data:
            old_sub = current.data.get("subscription_id")
            print(f"🔍 Suscripción anterior encontrada: {old_sub}")
        else:
            print("ℹ️ Cliente sin suscripción previa activa.")

        # -------------------------------------------------------------
        # 2️⃣ Crear nueva sesión de checkout en Stripe
        # -------------------------------------------------------------
        print("🚀 Creando nueva sesión de checkout en Stripe...")
        success_url = _ensure_success_url_has_session_id(
            os.getenv("STRIPE_SUCCESS_URL", "https://evolvianai.net/success")
        )
        metadata = {"plan_id": plan_id}
        if old_sub:
            # Evita estado huérfano en DB si el checkout no termina:
            # preservamos la sub anterior dentro de la sesión.
            metadata["previous_subscription_id"] = old_sub

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            mode="subscription",
            allow_promotion_codes=True,
            success_url=success_url,
            cancel_url=os.getenv("STRIPE_CANCEL_URL", "https://evolvianai.net/cancel"),
            client_reference_id=client_id,
            customer_email=email,  # ayuda a vincular usuario con cliente en Stripe
            metadata=metadata
        )

        print(f"✅ Sesión creada correctamente con URL: {session.url}")
        print(f"📦 Stripe Session ID: {session.id}")
        return {"url": session.url}

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error creando sesión de checkout:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Checkout session creation failed.")
