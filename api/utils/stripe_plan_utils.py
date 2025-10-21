import stripe
import os
from dotenv import load_dotenv
from api.config.config import supabase

load_dotenv()

# =====================================================
# 🔐 Configuración base de Stripe
# =====================================================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# =====================================================
# 🧩 Mapeo entre planes Evolvian y precios Stripe
# =====================================================

PRICE_MAP = {
    "free": None,  # No tiene Stripe ID
    "starter": os.getenv("STRIPE_PRICE_STARTER_ID", "price_starter_test"),
    "premium": os.getenv("STRIPE_PRICE_PREMIUM_ID", "price_premium_test"),
    "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL_ID", "price_white_label_test"),
}


# =====================================================
# 🔍 Utilidades para traducir entre plan interno ↔ Stripe
# =====================================================
def get_price_id_from_plan(plan_id: str) -> str | None:
    """Devuelve el price_id de Stripe a partir del plan interno Evolvian."""
    return PRICE_MAP.get(plan_id)


def get_plan_from_price_id(price_id: str) -> str | None:
    """Devuelve el plan Evolvian a partir de un price_id de Stripe."""
    for plan, pid in PRICE_MAP.items():
        if pid == price_id:
            return plan
    return None


# =====================================================
# 🔁 Cambiar plan de suscripción (upgrade o downgrade)
# =====================================================
def modify_subscription_plan(subscription_id: str, new_price_id: str, downgrade: bool = False):
    """
    Cambia el precio de una suscripción activa.
    - Si downgrade=True → sin prorrateo (aplica al siguiente ciclo)
    - Si upgrade → prorrateo inmediato
    """
    try:
        if not subscription_id or not new_price_id:
            raise ValueError("subscription_id y new_price_id son requeridos")

        print(f"🔁 Modificando suscripción {subscription_id} con nuevo precio {new_price_id}")

        subscription = stripe.Subscription.retrieve(subscription_id)
        current_item_id = subscription["items"]["data"][0]["id"]

        updated = stripe.Subscription.modify(
            subscription_id,
            items=[{"id": current_item_id, "price": new_price_id}],
            proration_behavior="none" if downgrade else "create_prorations",
        )

        print(f"✅ Suscripción actualizada correctamente ({'downgrade' if downgrade else 'upgrade'})")
        return updated

    except stripe.error.StripeError as e:
        print(f"❌ Error de Stripe al modificar suscripción: {e.user_message or e}")
        raise
    except Exception as e:
        print(f"🔥 Error inesperado al modificar suscripción: {e}")
        raise


# =====================================================
# ⏳ Cancelar suscripción al final del período
# =====================================================
def cancel_subscription_at_period_end(subscription_id: str):
    """
    Marca una suscripción para cancelarse al final del ciclo actual (cancel_at_period_end=True).
    """
    try:
        if not subscription_id:
            raise ValueError("subscription_id es requerido")

        print(f"🕒 Solicitando cancelación diferida para suscripción {subscription_id}...")

        updated = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )

        print(f"✅ cancel_at_period_end activado: {updated['cancel_at_period_end']}")
        return updated

    except stripe.error.InvalidRequestError as e:
        print(f"⚠️ Error al cancelar al final del ciclo (suscripción no encontrada o inválida): {e}")
        return None
    except Exception as e:
        print(f"❌ Error al cancelar suscripción al final del ciclo: {e}")
        raise


# =====================================================
# 💥 Cancelar suscripción inmediatamente si está activa
# =====================================================
async def cancel_subscription_immediately_if_exists(subscription_id: str):
    """
    Cancela inmediatamente una suscripción activa en Stripe (sin esperar el fin del ciclo).
    """
    try:
        if not subscription_id:
            print("⚠️ No se proporcionó subscription_id")
            return

        sub = stripe.Subscription.retrieve(subscription_id)

        if sub.status in ["active", "trialing", "incomplete"]:
            stripe.Subscription.delete(subscription_id)
            print(f"🧹 Suscripción {subscription_id} cancelada inmediatamente en Stripe.")
        else:
            print(f"ℹ️ Suscripción {subscription_id} no está activa, no se requiere acción.")

    except stripe.error.InvalidRequestError:
        print(f"⚠️ Suscripción {subscription_id} ya no existe en Stripe.")
    except Exception as e:
        print(f"❌ Error al cancelar suscripción inmediatamente: {e}")
        raise

def get_plan_from_price_id(price_id: str):
    plans = {
        "price_free": "free",
        "price_starter": "starter",
        "price_premium": "premium",
    }
    return plans.get(price_id, "free")

