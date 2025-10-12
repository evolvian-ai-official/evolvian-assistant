from fastapi import APIRouter, Request, Response, status
import os
import stripe
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import (
    update_client_plan_by_id,
    get_client_id_by_subscription_id
)

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret
        )
        print(f"✅ Webhook recibido: {event['type']}")
    except stripe.error.SignatureVerificationError:
        print("❌ Firma inválida de Stripe")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"🔥 Error general procesando webhook: {e}")
        return Response(status_code=500)

    try:
        # 🎯 Evento: Checkout completado
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            client_id = session.get("client_reference_id")
            plan_id = session.get("metadata", {}).get("plan_id")
            subscription_id = session.get("subscription")

            if client_id and plan_id and subscription_id:
                print(f"🎉 Cliente {client_id} activó plan '{plan_id}' (subscription_id: {subscription_id})")
                await update_client_plan_by_id(client_id, plan_id, subscription_id)
            else:
                print("⚠️ Datos faltantes en checkout.session.completed")

        # 💳 Evento: Factura pagada → obtener fechas reales
        elif event["type"] == "invoice.paid":
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")

            if not subscription_id:
                print("⚠️ invoice.paid sin subscription_id")
                return {"status": "skipped"}

            client_id = await get_client_id_by_subscription_id(subscription_id)
            if not client_id:
                print(f"⚠️ No se encontró client_id para subscription {subscription_id}")
                return {"status": "skipped"}

            subscription = stripe.Subscription.retrieve(subscription_id)
            plan_id = subscription.get("metadata", {}).get("plan_id") or "unknown"
            print(f"📅 invoice.paid → actualizando plan '{plan_id}' y fechas para {client_id}")
            await update_client_plan_by_id(client_id, plan_id, subscription_id)

        # 🔻 Evento: Suscripción cancelada (Stripe o cliente)
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            subscription_id = subscription.get("id")
            status_stripe = subscription.get("status")

            print(f"🧹 Suscripción eliminada: {subscription_id} (estado: {status_stripe})")

            # 🛡️ Ignorar si la suscripción nunca estuvo activa
            if status_stripe in ["incomplete", "incomplete_expired", "canceled"]:
                print(f"⏩ Ignorando suscripción cancelada sin activación real: {subscription_id}")
                return {"status": "skipped"}

            client_id = await get_client_id_by_subscription_id(subscription_id)
            if client_id:
                print(f"⬇️ Downgrade automático a FREE para cliente {client_id}")
                await update_client_plan_by_id(client_id, "free")
            else:
                print(f"⚠️ No se encontró client_id para subscription_id: {subscription_id}")

        else:
            print(f"ℹ️ Evento no manejado: {event['type']}")

    except Exception as e:
        print(f"❌ Error en procesamiento del evento {event.get('type', 'unknown')}: {e}")

    return {"status": "ok"}

@router.get("/stripe/ping")
async def ping_stripe_webhook():
    return {"message": "✅ Stripe Webhook activo"}
