from fastapi import APIRouter, Request, Response, status
import os
import stripe
from datetime import datetime, timezone
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import (
    update_client_plan_by_id,
    get_client_id_by_subscription_id,
    supabase
)
from api.utils.stripe_plan_utils import get_plan_from_price_id

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
        print(f"🔥 Error procesando webhook: {e}")
        return Response(status_code=500)

    try:
        # -------------------------------------------------------------
        # 1️⃣ checkout.session.completed → Nueva suscripción confirmada
        # -------------------------------------------------------------
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            client_id       = session.get("client_reference_id")
            plan_id         = session.get("metadata", {}).get("plan_id")
            subscription_id = session.get("subscription")

            if client_id and plan_id and subscription_id:
                print(f"🎉 Cliente {client_id} activó plan '{plan_id}' (sub: {subscription_id})")

                # Actualizar el cliente con el nuevo plan y sub
                await update_client_plan_by_id(client_id, plan_id, subscription_id)

                # Obtener la suscripción vieja marcada como pendiente
                rec = supabase.table("client_settings").select("pending_deleted_subscription_id").eq("client_id", client_id).execute()
                old_sub = None
                if rec.data and rec.data[0].get("pending_deleted_subscription_id"):
                    old_sub = rec.data[0]["pending_deleted_subscription_id"]

                # Cancelar la vieja si existe
                if old_sub:
                    try:
                        print(f"🧹 Cancelando suscripción anterior {old_sub} (upgrade confirmado)")
                        stripe.Subscription.delete(old_sub)
                        print(f"✅ Suscripción {old_sub} cancelada exitosamente.")
                    except Exception as e:
                        print(f"⚠️ Falló al cancelar suscripción antigua {old_sub}: {e}")

                # Limpiar flags
                supabase.table("client_settings").update({
                    "upgrade_in_progress": False,
                    "scheduled_plan_id": None,
                    "pending_deleted_subscription_id": None
                }).eq("client_id", client_id).execute()
                print(f"🔄 Flags limpiados para cliente {client_id}")
            else:
                print("⚠️ checkout.session.completed con datos faltantes")

        # -------------------------------------------------------------
        # 2️⃣ invoice.paid / invoice.payment_succeeded → Confirmar ciclo
        # -------------------------------------------------------------
        elif event["type"] in ["invoice.paid", "invoice.payment_succeeded", "invoice_payment.paid"]:
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                print("⚠️ Evento de invoice sin subscription_id")
                return Response(status_code=200)

            client_id = await get_client_id_by_subscription_id(subscription_id)
            if not client_id:
                print(f"⚠️ No se encontró client_id para {subscription_id}")
                return Response(status_code=200)

            subscription = stripe.Subscription.retrieve(subscription_id, expand=["items.data"])
            start_ts = subscription.get("current_period_start")
            end_ts   = subscription.get("current_period_end")
            price_id = subscription["items"]["data"][0]["price"]["id"]
            plan_id  = get_plan_from_price_id(price_id) or "unknown"

            subscription_start = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat() if start_ts else None
            subscription_end   = datetime.fromtimestamp(end_ts,   tz=timezone.utc).isoformat() if end_ts   else None

            print(f"📅 Ciclo confirmado para cliente {client_id}: {subscription_start} → {subscription_end} ({plan_id})")

            supabase.table("client_settings").update({
                "plan_id": plan_id,
                "subscription_id": subscription_id,
                "subscription_start": subscription_start,
                "subscription_end": subscription_end,
                "cancellation_requested_at": None
            }).eq("client_id", client_id).execute()

        # -------------------------------------------------------------
        # 3️⃣ customer.subscription.updated → Cancel-at-period-end
        # -------------------------------------------------------------
        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            subscription_id      = subscription.get("id")
            cancel_at_period_end = subscription.get("cancel_at_period_end", False)

            client_id = await get_client_id_by_subscription_id(subscription_id)
            if not client_id:
                print(f"⚠️ No se encontró client_id para {subscription_id}")
                return Response(status_code=200)

            if cancel_at_period_end:
                cancel_at_ts   = subscription.get("cancel_at")
                period_end_ts  = subscription.get("current_period_end")
                end_ts         = cancel_at_ts or period_end_ts
                cancel_date    = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat() if end_ts else None

                print(f"⏳ Cliente {client_id} programó cancelación para {cancel_date}")
                supabase.table("client_settings").update({
                    "cancellation_requested_at": datetime.utcnow().isoformat(),
                    "subscription_end": cancel_date
                }).eq("client_id", client_id).execute()
            else:
                print(f"♻️ Suscripción {subscription_id} actualizada sin cancelación programada.")
                supabase.table("client_settings").update({
                    "cancellation_requested_at": None
                }).eq("client_id", client_id).execute()

        # -------------------------------------------------------------
        # 4️⃣ customer.subscription.deleted → Manejo de bajas
        # -------------------------------------------------------------
        elif event["type"] == "customer.subscription.deleted":
            subscription   = event["data"]["object"]
            subscription_id = subscription.get("id")
            status_stripe   = subscription.get("status")
            customer_id     = subscription.get("customer")

            print(f"🧹 Suscripción finalizada: {subscription_id} ({status_stripe})")

            if status_stripe in ["incomplete", "incomplete_expired"]:
                print("⏩ Ignorando suscripción no activa.")
                return Response(status_code=200)

            client_id = await get_client_id_by_subscription_id(subscription_id)
            if not client_id:
                print(f"⚠️ No se encontró client_id para {subscription_id}")
                return Response(status_code=200)

            rec = supabase.table("client_settings").select(
                "pending_deleted_subscription_id", "upgrade_in_progress"
            ).eq("client_id", client_id).execute()
            pending_deleted = None
            in_progress     = False
            if rec.data and len(rec.data) > 0:
                pending_deleted = rec.data[0].get("pending_deleted_subscription_id")
                in_progress     = bool(rec.data[0].get("upgrade_in_progress", False))

            print(f"🔍 pending_deleted_subscription_id = {pending_deleted}, upgrade_in_progress = {in_progress}")

            # Si es la vieja del upgrade → ignorar downgrade
            if subscription_id == pending_deleted or in_progress:
                print("🚫 Ignorando evento deleted: corresponde a una suscripción vieja o upgrade en curso.")
                supabase.table("client_settings").update({
                    "pending_deleted_subscription_id": None,
                    "upgrade_in_progress": False
                }).eq("client_id", client_id).execute()
                return Response(status_code=200)

            # Verificar si quedan suscripciones activas
            active_subs = stripe.Subscription.list(customer=customer_id, status="active", limit=1)
            has_active = bool(active_subs.data)
            print(f"🔍 has_active_subscriptions = {has_active}")

            if has_active:
                print(f"🚫 Downgrade cancelado (otra sub activa) para cliente {client_id}")
                return Response(status_code=200)

            # Sin sub activa → downgrade automático
            print(f"⬇️ Downgrade automático a FREE para cliente {client_id}")
            supabase.table("client_settings").update({
                "plan_id": "free",
                "subscription_id": None,
                "subscription_start": None,
                "subscription_end": None,
                "cancellation_requested_at": None,
                "scheduled_plan_id": None,
                "pending_deleted_subscription_id": None,
                "upgrade_in_progress": False
            }).eq("client_id", client_id).execute()

        else:
            print(f"ℹ️ Evento no manejado: {event['type']}")

    except Exception as e:
        print(f"❌ Error procesando evento {event.get('type', 'unknown')}: {e}")

    return Response(status_code=200)
