# api/routes/create_checkout_session.py
from fastapi import APIRouter, Request
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import supabase
import traceback

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
print(f"🔐 Stripe API Key (inicio): {stripe.api_key[:10] if stripe.api_key else '❌ NOT SET'}...")

@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    client_id = data.get("client_id")
    plan_id = data.get("plan_id")
    stripe_price_id = data.get("price_id")  # opcional
    email = data.get("email")

    print("📥 Recibiendo petición para crear checkout session...")
    print(f"🧾 Datos recibidos: client_id={client_id}, plan_id={plan_id}, price_id={stripe_price_id}, email={email}")

    # ✅ Lookup de precios automático si no se envía desde el frontend
    plan_lookup = {
        "starter": os.getenv("STRIPE_PRICE_STARTER_ID"),
        "premium": os.getenv("STRIPE_PRICE_PREMIUM_ID"),
        "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL_ID")
    }

    # Fallback automático
    if not stripe_price_id:
        stripe_price_id = plan_lookup.get(plan_id)
        print(f"🔄 Usando price_id automático para plan '{plan_id}': {stripe_price_id}")

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

    # Validación final
    if not client_id or not plan_id or not stripe_price_id:
        print("⚠️ Faltan parámetros obligatorios para crear la sesión de checkout.")
        return {"error": "Missing required parameters."}

    try:
        print(f"🔎 Creando sesión para plan '{plan_id}' y cliente '{client_id}'")

        # -------------------------------------------------------------
        # 1️⃣ Marcar upgrade en progresod
        # -------------------------------------------------------------
        print(f"🟡 Marcando upgrade_in_progress=True para cliente {client_id}")
        res_update = supabase.table("client_settings").update({
            "upgrade_in_progress": True
        }).eq("client_id", client_id).execute()
        print(f"🧩 Resultado update upgrade_in_progress: {res_update}")

        # -------------------------------------------------------------
        # 2️⃣ Obtener la suscripción anterior (si existe)
        # -------------------------------------------------------------
        current = supabase.table("client_settings").select("subscription_id").eq("client_id", client_id).execute()
        old_sub = None
        if current.data and len(current.data) > 0:
            old_sub = current.data[0].get("subscription_id")
            print(f"🔍 Suscripción anterior encontrada: {old_sub}")
        else:
            print("ℹ️ Cliente sin suscripción previa activa.")

        # -------------------------------------------------------------
        # 3️⃣ Guardar la suscripción antigua como pendiente de borrado
        # -------------------------------------------------------------
        if old_sub:
            print(f"⚠️ Se pospone cancelación de la suscripción antigua ({old_sub}) hasta que la nueva esté activa.")
            res_pending = supabase.table("client_settings").update({
                "pending_deleted_subscription_id": old_sub
            }).eq("client_id", client_id).execute()
            print(f"🧩 Resultado update pending_deleted_subscription_id: {res_pending}")

        # -------------------------------------------------------------
        # 4️⃣ Crear nueva sesión de checkout en Stripe
        # -------------------------------------------------------------
        print("🚀 Creando nueva sesión de checkout en Stripe...")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=os.getenv("STRIPE_SUCCESS_URL", "https://evolvianai.net/success"),
            cancel_url=os.getenv("STRIPE_CANCEL_URL", "https://evolvianai.net/cancel"),
            client_reference_id=client_id,
            customer_email=email,  # ayuda a vincular usuario con cliente en Stripe
            metadata={"plan_id": plan_id}
        )

        print(f"✅ Sesión creada correctamente con URL: {session.url}")
        print(f"📦 Stripe Session ID: {session.id}")
        return {"url": session.url}

    except Exception as e:
        print("❌ Error creando sesión de checkout:")
        traceback.print_exc()
        return {"error": str(e)}
