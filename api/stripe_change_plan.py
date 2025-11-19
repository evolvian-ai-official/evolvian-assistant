from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from api.config.config import supabase
from api.utils.stripe_plan_utils import modify_subscription_plan, cancel_subscription_at_period_end
import stripe

load_dotenv()
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

plan_lookup = {
    "starter": os.getenv("STRIPE_PRICE_STARTER_ID"),
    "premium": os.getenv("STRIPE_PRICE_PREMIUM_ID"),
    "white_label": os.getenv("STRIPE_PRICE_WHITE_LABEL_ID"),
}


@router.post("/change-plan")
async def change_plan(request: Request):
    print("🔄 [CHANGE PLAN] Recibiendo solicitud de cambio de plan...")

    try:
        data = await request.json()
        client_id = data.get("client_id")
        new_plan_id = data.get("new_plan_id")

        if not client_id or not new_plan_id:
            raise HTTPException(status_code=400, detail="Faltan parámetros requeridos.")

        print(f"➡️ Cliente {client_id} solicita cambio a plan '{new_plan_id}'")

        # 📦 Obtener datos actuales del cliente
        res = (
            supabase.table("client_settings")
            .select("plan_id, subscription_id")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )

        if not res or not res.data:
            raise HTTPException(status_code=404, detail="Cliente no encontrado en client_settings")

        current_plan = res.data.get("plan_id")
        subscription_id = res.data.get("subscription_id")
        print(f"🔍 Plan actual: {current_plan} | Subscription ID: {subscription_id}")

        if not subscription_id:
            raise HTTPException(status_code=400, detail="El cliente no tiene una suscripción activa")

        # ⚖️ Clasificar tipo de cambio
        is_upgrade = (current_plan == "starter" and new_plan_id == "premium")
        is_downgrade = (current_plan == "premium" and new_plan_id == "starter")
        is_to_free = (new_plan_id == "free")

        # ======================================================
        # 🧩 CASO 1: Downgrade a FREE (cancelar suscripción)
        # ======================================================
        if is_to_free:
            print("⏳ [FREE] Programando cancelación al final del ciclo...")

            try:
                subscription = stripe.Subscription.retrieve(subscription_id, expand=["items.data"])
                period_end_ts = (
                    subscription.get("current_period_end")
                    or (subscription["items"]["data"][0].get("current_period_end") if subscription.get("items") else None)
                )

                if not period_end_ts:
                    raise ValueError("Stripe no devolvió current_period_end")

                period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
                result = cancel_subscription_at_period_end(subscription_id)

                if result and result.get("cancel_at_period_end"):
                    print(f"✅ Stripe marcó cancel_at_period_end=True para {subscription_id}")
                else:
                    print(f"⚠️ Stripe no devolvió confirmación clara, aplicando fallback local.")

            except Exception as e:
                print(f"⚠️ Error cancelando en Stripe: {e}")
                period_end = datetime.now(timezone.utc) + timedelta(days=30)

            # 🔄 Actualizar Supabase
            supabase.table("client_settings").update({
                "scheduled_plan_id": "free",
                "plan_id": current_plan,
                "cancellation_requested_at": datetime.now(timezone.utc).isoformat(),
                "subscription_end": period_end.isoformat()
            }).eq("client_id", client_id).execute()

            print(f"✅ Downgrade a FREE programado hasta {period_end}")
            return JSONResponse({
                "status": "scheduled_cancel",
                "message": f"Your {current_plan.capitalize()} plan will be downgraded to Free on {period_end.strftime('%b %d, %Y')}."
            })

        # ======================================================
        # 🧩 CASO 2: Downgrade entre planes pagos (Premium → Starter)
        # ======================================================
        if is_downgrade:
            print("⏳ [DOWNGRADE] Programando cambio Premium → Starter al final del ciclo...")

            try:
                subscription = stripe.Subscription.retrieve(subscription_id, expand=["items.data"])
                period_end_ts = (
                    subscription.get("current_period_end")
                    or (subscription["items"]["data"][0].get("current_period_end") if subscription.get("items") else None)
                )

                if not period_end_ts:
                    raise ValueError("Stripe no devolvió current_period_end")

                period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)

                result = cancel_subscription_at_period_end(subscription_id)
                if result and result.get("cancel_at_period_end"):
                    print(f"✅ Stripe marcó cancel_at_period_end=True para {subscription_id}")
                else:
                    print(f"⚠️ Stripe no devolvió confirmación clara, aplicando fallback local.")
            except Exception as e:
                print(f"⚠️ Error al cancelar en Stripe: {e}")
                period_end = datetime.now(timezone.utc) + timedelta(days=30)

            # 🔄 Actualizar Supabase
            supabase.table("client_settings").update({
                "scheduled_plan_id": new_plan_id,
                "plan_id": current_plan,
                "cancellation_requested_at": datetime.now(timezone.utc).isoformat(),
                "subscription_end": period_end.isoformat()
            }).eq("client_id", client_id).execute()

            print(f"✅ Downgrade Premium → Starter programado hasta {period_end}")
            return JSONResponse({
                "status": "scheduled_downgrade",
                "message": f"Your Premium plan will be downgraded to Starter on {period_end.strftime('%b %d, %Y')}."
            })

        # ======================================================
        # ⚡ CASO 3: Upgrade inmediato
        # ======================================================
        price_id = plan_lookup.get(new_plan_id)
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan inválido o sin price_id configurado")

        print(f"⚡ [UPGRADE] Ejecutando cambio inmediato a {new_plan_id}...")
        result = modify_subscription_plan(subscription_id, price_id, downgrade=False)
        if not result:
            raise HTTPException(status_code=500, detail="Error al modificar la suscripción en Stripe")

        supabase.table("client_settings").update({
            "plan_id": new_plan_id,
            "cancellation_requested_at": None,
            "scheduled_plan_id": None
        }).eq("client_id", client_id).execute()

        print(f"✅ Cambio de plan aplicado inmediatamente: {new_plan_id}")
        return JSONResponse({
            "status": "ok",
            "message": f"Suscripción actualizada a {new_plan_id.capitalize()}"
        })

    # ======================================================
    # ❌ Manejo de errores global
    # ======================================================
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"🔥 Error interno en /change-plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
