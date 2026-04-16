# api/routes/create_checkout_session.py
from fastapi import APIRouter, Request, HTTPException
import stripe
import os
from dotenv import load_dotenv
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
from api.utils.effective_plan import get_client_override_plan_id
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
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "session_id"
    ]
    rebuilt_query = urlencode(query_pairs)
    session_param = "session_id={CHECKOUT_SESSION_ID}"
    if rebuilt_query:
        rebuilt_query = f"{rebuilt_query}&{session_param}"
    else:
        rebuilt_query = session_param
    return urlunparse(parsed._replace(query=rebuilt_query))


def _origin_base_url(request: Request) -> str | None:
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        return origin.rstrip("/")

    referer = (request.headers.get("referer") or "").strip()
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    return None


def _is_localhost_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    return hostname in {"localhost", "127.0.0.1", "0.0.0.0"}


def _resolve_checkout_redirect_url(request: Request, env_var_name: str, default_path: str) -> str:
    configured_url = (os.getenv(env_var_name) or "").strip()
    request_origin = _origin_base_url(request)

    # Si producción está apuntando por error a localhost en env, preferimos el origin real del navegador.
    if request_origin and not _is_localhost_url(request_origin) and _is_localhost_url(configured_url):
        return f"{request_origin}{default_path}"

    if configured_url:
        return configured_url

    if request_origin:
        return f"{request_origin}{default_path}"

    return f"https://evolvianai.net{default_path}"


@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    client_id = data.get("client_id")
    plan_id = str(data.get("plan_id") or "").strip().lower()
    stripe_price_id = data.get("price_id")  # no confiable desde cliente
    email = str(data.get("email") or "").strip() or None

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
    override_plan_id = get_client_override_plan_id(client_id, supabase_client=supabase)
    if override_plan_id:
        raise HTTPException(
            status_code=409,
            detail="Plan managed internally for this client; Stripe checkout is disabled.",
        )

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
            _resolve_checkout_redirect_url(request, "STRIPE_SUCCESS_URL", "/dashboard")
        )
        cancel_url = _resolve_checkout_redirect_url(request, "STRIPE_CANCEL_URL", "/settings")
        metadata = {"plan_id": plan_id}
        if old_sub:
            # Evita estado huérfano en DB si el checkout no termina:
            # preservamos la sub anterior dentro de la sesión.
            metadata["previous_subscription_id"] = old_sub

        session_payload = {
            "payment_method_types": ["card"],
            "line_items": [{"price": stripe_price_id, "quantity": 1}],
            "mode": "subscription",
            "allow_promotion_codes": True,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_id,
            "metadata": metadata,
        }
        if email:
            session_payload["customer_email"] = email

        session = stripe.checkout.Session.create(
            **session_payload
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
