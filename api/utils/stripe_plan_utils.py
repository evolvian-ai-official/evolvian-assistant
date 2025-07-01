import stripe
import os
from dotenv import load_dotenv
from api.config.config import supabase

load_dotenv()

# 🔐 Clave secreta de Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# -------------------------------
# 🔁 Cambio entre Starter y Premium con prorrateo
# -------------------------------
def modify_subscription_plan(subscription_id: str, new_price_id: str):
    try:
        if not subscription_id or not new_price_id:
            raise ValueError("subscription_id y new_price_id son requeridos")

        print(f"🔁 Modificando suscripción {subscription_id} con nuevo precio {new_price_id}")

        subscription = stripe.Subscription.retrieve(subscription_id)
        current_item_id = subscription['items']['data'][0]['id']

        updated = stripe.Subscription.modify(
            subscription_id,
            items=[{
                "id": current_item_id,
                "price": new_price_id
            }],
            proration_behavior="create_prorations"
        )

        print("✅ Suscripción actualizada con prorrateo")
        return updated

    except Exception as e:
        print("❌ Error al modificar suscripción:", e)
        raise


# -------------------------------
# ⏳ Cancelar suscripción al final del período
# -------------------------------
def cancel_subscription_at_period_end(subscription_id: str):
    try:
        if not subscription_id:
            raise ValueError("subscription_id es requerido")

        print(f"🕒 Cancelando suscripción {subscription_id} al final del ciclo...")

        updated = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )

        print(f"✅ Cancelación programada correctamente. Estado: {updated['status']}")
        return updated

    except Exception as e:
        print("❌ Error al cancelar suscripción al final del ciclo:", e)
        raise


# -------------------------------
# 💥 Cancelar suscripción inmediatamente si aún está activa
# -------------------------------
async def cancel_subscription_immediately_if_exists(subscription_id: str):
    try:
        if not subscription_id:
            print("⚠️ No se proporcionó subscription_id")
            return

        sub = stripe.Subscription.retrieve(subscription_id)

        if sub.status in ["active", "trialing", "incomplete"]:
            stripe.Subscription.delete(subscription_id)
            print(f"🧹 Suscripción {subscription_id} cancelada inmediatamente en Stripe")
        else:
            print(f"ℹ️ Suscripción {subscription_id} no está activa. No se requiere acción.")

    except stripe.error.InvalidRequestError:
        print(f"⚠️ Suscripción {subscription_id} ya no existe en Stripe.")
    except Exception as e:
        print(f"❌ Error al cancelar suscripción inmediatamente: {e}")
        raise
