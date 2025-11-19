from fastapi import APIRouter, Request
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import supabase

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
        print("⚠️ Faltan parámetros obligatorios para crear la sesión de checkout.")
        return {"error": "Missing required parameters."}

    try:
        print("📥 Recibiendo petición para crear checkout session...")
        print(f"🔎 Creando sesión para plan '{plan_id}' y cliente '{client_id}'")

        # -------------------------------------------------------------
        # 1️⃣ Marcar upgrade en progreso
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
            metadata={"plan_id": plan_id}
        )

        print(f"✅ Sesión creada correctamente: {session.url}")
        return {"url": session.url}

    except Exception as e:
        print(f"❌ Error creando sesión de checkout: {e}")
        return {"error": str(e)}
