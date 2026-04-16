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
from api.utils.calendar_plan_cleanup import disconnect_calendar_features_for_plan
from api.utils.stripe_plan_utils import get_plan_from_price_id, create_subscription_for_customer

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


def _log_billing_recovery_event(
    *,
    client_id: str,
    event_name: str,
    details: dict | None = None,
):
    try:
        event_row = {
            "client_id": client_id,
            "role": "assistant",
            "content": event_name,
            "channel": "system",
            "source_type": "billing_alert",
            "provider": "internal",
            "status": "error",
            "metadata": details or {},
            "session_id": "__billing__",
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("history").insert(event_row).execute()
        print(f"📝 Billing recovery event logged for client {client_id}: {event_name}")
    except Exception as log_error:
        print(f"⚠️ No se pudo registrar billing recovery event para {client_id}: {log_error}")


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
            session_metadata = session.get("metadata", {}) or {}
            plan_id         = session_metadata.get("plan_id")
            subscription_id = session.get("subscription")

            if client_id and plan_id and subscription_id:
                print(f"🎉 Cliente {client_id} activó plan '{plan_id}' (sub: {subscription_id})")

                # Actualizar el cliente con el nuevo plan y sub
                await update_client_plan_by_id(client_id, plan_id, subscription_id)

                # Suscripción anterior: primero metadata de la sesión (nuevo),
                # luego fallback legacy de DB.
                old_sub = session_metadata.get("previous_subscription_id")
                if not old_sub:
                    rec = (
                        supabase.table("client_settings")
                        .select("pending_deleted_subscription_id")
                        .eq("client_id", client_id)
                        .maybe_single()
                        .execute()
                    )
                    if rec and rec.data:
                        old_sub = rec.data.get("pending_deleted_subscription_id")

                # Cancelar la vieja si existe
                if old_sub and old_sub != subscription_id:
                    try:
                        print(f"🧹 Cancelando suscripción anterior {old_sub} (upgrade confirmado)")
                        stripe.Subscription.delete(old_sub)
                        print(f"✅ Suscripción {old_sub} cancelada exitosamente.")
                    except Exception as e:
                        print(f"⚠️ Falló al cancelar suscripción antigua {old_sub}: {e}")

                # Limpiar flags legacy
                supabase.table("client_settings").update({
                    "upgrade_in_progress": False,
                    "scheduled_plan_id": None,
                    "pending_deleted_subscription_id": None
                }).eq("client_id", client_id).execute()
                print(f"🔄 Flags limpiados para cliente {client_id}")
            else:
                print("⚠️ checkout.session.completed con datos faltantes")

        # -------------------------------------------------------------
        # 2️⃣ checkout.session.expired → limpiar flags legacy huérfanos
        # -------------------------------------------------------------
        elif event["type"] == "checkout.session.expired":
            session = event["data"]["object"]
            client_id = session.get("client_reference_id")
            if client_id:
                print(f"⌛ Checkout expirado para cliente {client_id}; limpiando flags legacy")
                supabase.table("client_settings").update({
                    "upgrade_in_progress": False,
                    "pending_deleted_subscription_id": None
                }).eq("client_id", client_id).execute()

        # -------------------------------------------------------------
        # 3️⃣ invoice.paid / invoice.payment_succeeded → Confirmar ciclo
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
            disconnect_calendar_features_for_plan(
                client_id,
                base_plan_id=plan_id,
                supabase_client=supabase,
            )

        # -------------------------------------------------------------
        # 4️⃣ customer.subscription.updated → Cancel-at-period-end
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
        # 5️⃣ customer.subscription.deleted → Manejo de bajas
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
                "scheduled_plan_id, pending_deleted_subscription_id, upgrade_in_progress"
            ).eq("client_id", client_id).execute()
            scheduled_plan_id = None
            pending_deleted = None
            in_progress     = False
            if rec.data and len(rec.data) > 0:
                scheduled_plan_id = rec.data[0].get("scheduled_plan_id")
                pending_deleted = rec.data[0].get("pending_deleted_subscription_id")
                in_progress     = bool(rec.data[0].get("upgrade_in_progress", False))

            print(
                f"🔍 scheduled_plan_id = {scheduled_plan_id}, "
                f"pending_deleted_subscription_id = {pending_deleted}, upgrade_in_progress = {in_progress}"
            )

            # Verificar si quedan suscripciones activas
            active_subs = stripe.Subscription.list(customer=customer_id, status="active", limit=1)
            has_active = bool(active_subs.data)
            print(f"🔍 has_active_subscriptions = {has_active}")

            if has_active:
                # Si había estado legacy de upgrade, limpiarlo sin forzar downgrade.
                if subscription_id == pending_deleted or in_progress:
                    print("✅ Deleted de sub vieja durante upgrade; limpiando flags legacy.")
                    supabase.table("client_settings").update({
                        "pending_deleted_subscription_id": None,
                        "upgrade_in_progress": False
                    }).eq("client_id", client_id).execute()
                print(f"🚫 Downgrade cancelado (otra sub activa) para cliente {client_id}")
                return Response(status_code=200)

            if scheduled_plan_id and scheduled_plan_id != "free":
                try:
                    customer = stripe.Customer.retrieve(customer_id)
                    customer_invoice_settings = customer.get("invoice_settings") or {}
                    customer_default_pm = customer_invoice_settings.get("default_payment_method")
                    fallback_payment_method = (
                        customer_default_pm
                        or subscription.get("default_payment_method")
                        or None
                    )
                    new_subscription = create_subscription_for_customer(
                        customer_id,
                        scheduled_plan_id,
                        default_payment_method=fallback_payment_method,
                        metadata={
                            "client_id": client_id,
                            "plan_id": scheduled_plan_id,
                            "transition": "scheduled_downgrade",
                        },
                    )
                    start_ts = new_subscription.get("current_period_start")
                    end_ts = new_subscription.get("current_period_end")
                    new_subscription_id = new_subscription.get("id")
                    supabase.table("client_settings").update({
                        "plan_id": scheduled_plan_id,
                        "subscription_id": new_subscription_id,
                        "subscription_start": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat() if start_ts else None,
                        "subscription_end": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat() if end_ts else None,
                        "cancellation_requested_at": None,
                        "scheduled_plan_id": None,
                        "pending_deleted_subscription_id": None,
                        "upgrade_in_progress": False,
                    }).eq("client_id", client_id).execute()
                    disconnect_calendar_features_for_plan(
                        client_id,
                        base_plan_id=scheduled_plan_id,
                        supabase_client=supabase,
                    )
                    print(
                        f"✅ Downgrade programado materializado: cliente {client_id} → "
                        f"{scheduled_plan_id} (sub {new_subscription_id})"
                    )
                    return Response(status_code=200)
                except Exception as e:
                    print(
                        f"⚠️ No se pudo crear suscripción para downgrade programado "
                        f"{scheduled_plan_id} de cliente {client_id}: {e}"
                    )
                    _log_billing_recovery_event(
                        client_id=client_id,
                        event_name="scheduled_downgrade_recovery_needed",
                        details={
                            "previous_subscription_id": subscription_id,
                            "customer_id": customer_id,
                            "target_plan_id": scheduled_plan_id,
                            "reason": str(e),
                        },
                    )
                    print(f"⬇️ Fallback seguro a FREE para cliente {client_id} tras fallo de downgrade programado")
                    supabase.table("client_settings").update({
                        "plan_id": "free",
                        "subscription_id": None,
                        "subscription_start": None,
                        "subscription_end": None,
                        "cancellation_requested_at": None,
                        "scheduled_plan_id": scheduled_plan_id,
                        "pending_deleted_subscription_id": None,
                        "upgrade_in_progress": False,
                    }).eq("client_id", client_id).execute()
                    disconnect_calendar_features_for_plan(
                        client_id,
                        base_plan_id="free",
                        supabase_client=supabase,
                    )
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
            disconnect_calendar_features_for_plan(
                client_id,
                base_plan_id="free",
                supabase_client=supabase,
            )

        else:
            print(f"ℹ️ Evento no manejado: {event['type']}")

    except Exception as e:
        print(f"❌ Error procesando evento {event.get('type', 'unknown')}: {e}")

    return Response(status_code=200)
