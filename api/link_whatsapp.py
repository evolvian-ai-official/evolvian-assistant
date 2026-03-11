from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.template_sync import (
    discover_waba_phone_candidates,
    ensure_waba_app_subscription,
    extract_phone_effective_status,
    fetch_phone_number_metadata,
    get_active_whatsapp_channel,
    get_waba_subscription_status,
    is_phone_number_approved,
    resolve_waba_id_from_phone,
    sync_canonical_templates_for_client,
    validate_waba_phone_binding,
)
from api.security.whatsapp_token_crypto import encrypt_whatsapp_token
from datetime import datetime
import uuid
import re
import logging
import os
import requests
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from api.authz import get_current_user_id
from api.oauth_state import decode_signed_state, encode_signed_state

router = APIRouter()
logger = logging.getLogger(__name__)

# =====================================================
# HELPERS
# =====================================================

def get_client_id_from_user(auth_user_id: str) -> str:
    """
    Secure lookup of client_id from authenticated user.
    """
    user_res = (
        supabase.table("users")
        .select("id")
        .eq("id", auth_user_id)
        .execute()
    )

    if not user_res.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    client_res = (
        supabase.table("clients")
        .select("id")
        .eq("user_id", auth_user_id)
        .limit(1)
        .execute()
    )

    if not client_res.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return client_res.data[0]["id"]


def validate_e164(number: str) -> str:
    number = number.replace("whatsapp:", "").strip()

    if not number.startswith("+"):
        number = f"+{number}"

    if not re.match(r"^\+[1-9]\d{9,14}$", number):
        raise HTTPException(
            status_code=400,
            detail="Número inválido. Formato requerido: E.164"
        )

    return number


def _meta_graph_version() -> str:
    return str(os.getenv("META_GRAPH_VERSION") or "v22.0").strip() or "v22.0"


def _meta_app_id() -> str:
    value = str(os.getenv("META_APP_ID") or "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="meta_app_id_not_configured")
    return value


def _meta_app_secret() -> str:
    value = str(os.getenv("META_APP_SECRET") or "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="meta_app_secret_not_configured")
    return value


def _forwarded_scheme(request: Request) -> str:
    return (
        str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        or request.url.scheme
        or "https"
    )


def _forwarded_host(request: Request) -> str:
    return (
        str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
        or str(request.headers.get("host") or "").strip()
        or request.url.netloc
    )


def _request_origin(request: Request) -> str:
    return f"{_forwarded_scheme(request)}://{_forwarded_host(request)}"


def _meta_callback_url(request: Request) -> str:
    configured = str(os.getenv("META_EMBEDDED_SIGNUP_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return f"{_request_origin(request)}/meta_embedded_signup/callback"


def _normalize_ui_return_url(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="ui_return_url_required")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="ui_return_url_invalid")
    return candidate


def _normalize_allowed_ui_origin(value: str) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None

    # Accept full URL entries (with path) and keep only origin.
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    # Accept host-only entries and host/path entries.
    host = candidate.split("/", 1)[0].strip().lower()
    if host:
        return host
    return None


def _is_allowed_ui_return_url(url: str) -> bool:
    allowed = {
        normalized
        for item in str(os.getenv("META_EMBEDDED_ALLOWED_UI_ORIGINS") or "").split(",")
        for normalized in [_normalize_allowed_ui_origin(item)]
        if normalized
    }
    if not allowed:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    host = parsed.netloc.lower()
    return origin in allowed or host in allowed


def _default_ui_return_url(request: Request) -> str:
    configured = str(os.getenv("META_EMBEDDED_SIGNUP_UI_RETURN_URL") or "").strip()
    if configured:
        return configured
    return f"{_request_origin(request)}/services/meta-apps"


def _append_query_params(url: str, additions: dict[str, str]) -> str:
    parsed = urlparse(url)
    items = [(k, v) for (k, v) in parse_qsl(parsed.query, keep_blank_values=True) if k not in additions]
    for key, value in additions.items():
        if value is None:
            continue
        items.append((key, str(value)))
    new_query = urlencode(items, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def _meta_scopes() -> str:
    configured = str(os.getenv("META_EMBEDDED_SIGNUP_SCOPES") or "").strip()
    if configured:
        return configured
    return "business_management,whatsapp_business_management,whatsapp_business_messaging"


def _build_meta_oauth_url(*, request: Request, state: str) -> str:
    params: dict[str, str] = {
        "client_id": _meta_app_id(),
        "redirect_uri": _meta_callback_url(request),
        "state": state,
        "response_type": "code",
        "scope": _meta_scopes(),
    }
    return f"https://www.facebook.com/{_meta_graph_version()}/dialog/oauth?{urlencode(params)}"


def _exchange_meta_code_for_token(*, request: Request, code: str) -> str:
    graph_version = _meta_graph_version()
    redirect_uri = _meta_callback_url(request)
    response = requests.get(
        f"https://graph.facebook.com/{graph_version}/oauth/access_token",
        params={
            "client_id": _meta_app_id(),
            "client_secret": _meta_app_secret(),
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=18,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str((payload.get("error") or {}).get("message") or "")
        except Exception:
            detail = response.text[:300]
        raise HTTPException(status_code=400, detail=f"meta_code_exchange_failed:{detail or 'unknown_error'}")

    payload = response.json() if response.content else {}
    access_token = str((payload or {}).get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="meta_code_exchange_missing_access_token")

    # Best effort: extend user token lifetime.
    try:
        long_lived_res = requests.get(
            f"https://graph.facebook.com/{graph_version}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": _meta_app_id(),
                "client_secret": _meta_app_secret(),
                "fb_exchange_token": access_token,
            },
            timeout=18,
        )
        if long_lived_res.status_code < 400:
            long_payload = long_lived_res.json() if long_lived_res.content else {}
            maybe_long_lived = str((long_payload or {}).get("access_token") or "").strip()
            if maybe_long_lived:
                access_token = maybe_long_lived
    except Exception:
        logger.warning("⚠️ Could not exchange Meta token to long-lived token")

    return access_token


def _sanitize_phone_for_matching(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _normalize_to_e164(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    digits = _sanitize_phone_for_matching(raw)
    if not digits:
        return None
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}"


def _pick_candidate_phone(candidates: list[dict], preferred_phone: str | None = None) -> dict | None:
    if not candidates:
        return None

    preferred_digits = _sanitize_phone_for_matching(preferred_phone)
    if preferred_digits:
        for row in candidates:
            display_digits = _sanitize_phone_for_matching(row.get("display_phone_number"))
            if display_digits and (display_digits.endswith(preferred_digits) or preferred_digits.endswith(display_digits)):
                return row

    return candidates[0]


def _link_whatsapp_channel_for_client(
    *,
    client_id: str,
    phone: str,
    provider: str,
    wa_phone_id: str | None,
    wa_token: str | None,
    wa_business_account_id: str | None,
) -> dict:
    if provider not in {"meta", "twilio"}:
        raise HTTPException(status_code=400, detail="Proveedor inválido")

    number = validate_e164(phone)
    now = datetime.utcnow().isoformat()
    resolved_waba_id = None
    waba_subscription = None
    phone_probe = None
    setup_progress = None

    if provider == "meta":
        if not wa_phone_id or not wa_token:
            raise HTTPException(status_code=400, detail="Meta requiere wa_phone_id y wa_token")

        provided_waba_id = str(wa_business_account_id or "").strip()
        if provided_waba_id:
            if not re.match(r"^\d{8,24}$", provided_waba_id):
                raise HTTPException(status_code=400, detail="wa_business_account_id inválido")
            resolved_waba_id = provided_waba_id
        else:
            resolved_waba_id = resolve_waba_id_from_phone(
                wa_phone_id=str(wa_phone_id or ""),
                wa_token=str(wa_token or ""),
            )
            if not resolved_waba_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No pudimos validar wa_business_account_id con el wa_phone_id/token proporcionados. "
                        "Verifica credenciales de Meta o envía wa_business_account_id."
                    ),
                )

        if not validate_waba_phone_binding(
            waba_id=str(resolved_waba_id or ""),
            wa_phone_id=str(wa_phone_id or ""),
            wa_token=str(wa_token or ""),
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo validar el vínculo wa_business_account_id + wa_phone_id con ese token. "
                    "Revisa permisos de Meta (WhatsApp Business Management)."
                ),
            )

        waba_subscription = ensure_waba_app_subscription(
            waba_id=str(resolved_waba_id or ""),
            wa_token=str(wa_token or ""),
        )
        if not bool(waba_subscription.get("success")):
            meta_error = str(waba_subscription.get("error") or "unknown_error")
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo suscribir la app al WABA. "
                    "Revisa permisos del token (business_management y whatsapp_business_management). "
                    f"Detalle Meta: {meta_error}"
                ),
            )

        phone_probe = fetch_phone_number_metadata(
            wa_phone_id=str(wa_phone_id or ""),
            wa_token=str(wa_token or ""),
        )
        subscription_probe = {
            "success": True,
            "subscribed": True,
            "app_count": 1 if not bool(waba_subscription.get("already_subscribed")) else None,
        }
        setup_progress = _build_setup_progress(
            channel_ready=True,
            binding_ok=True,
            subscription_probe=subscription_probe,
            phone_probe=phone_probe,
        )

    encrypted_wa_token = None
    if provider == "meta":
        try:
            encrypted_wa_token = encrypt_whatsapp_token(str(wa_token or ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="Meta requiere wa_token válido")
        except RuntimeError as crypto_error:
            raise HTTPException(status_code=500, detail=str(crypto_error))

    supabase.table("channels") \
        .update({
            "is_active": False,
            "archived_at": now,
            "archived_reason": "replaced_by_new_connection",
            "last_disconnected_at": now,
            "updated_at": now
        }) \
        .eq("client_id", client_id) \
        .eq("type", "whatsapp") \
        .execute()

    insert_payload = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "type": "whatsapp",
        "value": number,
        "provider": provider,
        "wa_phone_id": wa_phone_id,
        "wa_token": encrypted_wa_token,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "last_connected_at": now,
        "archived_at": None,
        "archived_reason": None,
        "last_disconnected_at": None
    }

    if resolved_waba_id:
        insert_payload["wa_business_account_id"] = resolved_waba_id

    try:
        insert_res = supabase.table("channels").insert(insert_payload).execute()
    except Exception as insert_error:
        if "wa_business_account_id" in insert_payload:
            logger.warning(
                "⚠️ channels.wa_business_account_id not available yet; retrying insert without cache | %s",
                insert_error,
            )
            insert_payload.pop("wa_business_account_id", None)
            insert_res = supabase.table("channels").insert(insert_payload).execute()
        else:
            raise

    if not insert_res.data:
        raise HTTPException(status_code=500, detail="Error creando canal")

    sync_summary = None
    if provider == "meta":
        try:
            sync_summary = sync_canonical_templates_for_client(client_id=client_id)
        except Exception as sync_error:
            logger.exception(
                "⚠️ WhatsApp linked but template provisioning failed | client_id=%s | error=%s",
                client_id,
                sync_error,
            )
            sync_summary = {
                "success": False,
                "client_id": client_id,
                "errors": [f"template_sync_error:{sync_error}"],
            }

    return {
        "success": True,
        "connected": True,
        "waba_subscription": waba_subscription,
        "phone_probe": phone_probe,
        "setup_complete": bool((setup_progress or {}).get("setup_complete")),
        "setup_progress": setup_progress,
        "template_sync": sync_summary,
    }


def _build_setup_progress(
    *,
    channel_ready: bool,
    binding_ok: bool,
    subscription_probe: dict | None,
    phone_probe: dict | None,
) -> dict:
    steps: list[dict] = []
    suggestions: list[str] = []

    if channel_ready:
        steps.append({
            "key": "channel_ready",
            "state": "done",
            "detail": "Credenciales base detectadas (WABA ID, Phone Number ID y token).",
        })
    else:
        steps.append({
            "key": "channel_ready",
            "state": "error",
            "detail": "Faltan credenciales base del canal para validar setup.",
        })
        suggestions.append(
            "Revisa que enviaste WABA ID, Phone Number ID y token permanente válidos."
        )

    if binding_ok:
        steps.append({
            "key": "waba_phone_binding",
            "state": "done",
            "detail": "WABA y Phone Number ID linkeados correctamente.",
        })
    else:
        steps.append({
            "key": "waba_phone_binding",
            "state": "error",
            "detail": "No se confirmó vínculo entre WABA y Phone Number ID.",
        })
        suggestions.append(
            "Verifica que el Phone Number ID pertenezca al WABA y que el token tenga `whatsapp_business_management`."
        )

    if subscription_probe is None:
        steps.append({
            "key": "waba_subscription",
            "state": "pending",
            "detail": "Suscripción de app al WABA pendiente.",
        })
    elif not bool(subscription_probe.get("success")):
        detail = str(subscription_probe.get("error") or "error_desconocido")
        steps.append({
            "key": "waba_subscription",
            "state": "error",
            "detail": f"No se pudo validar suscripción al WABA: {detail}",
        })
        suggestions.append(
            "Suscribe la app al WABA con `POST /{waba_id}/subscribed_apps` y revisa permisos `business_management`."
        )
    elif bool(subscription_probe.get("subscribed")):
        app_count = subscription_probe.get("app_count")
        app_msg = f" ({app_count} app(s) suscritas)." if app_count is not None else "."
        steps.append({
            "key": "waba_subscription",
            "state": "done",
            "detail": f"App suscrita al WABA{app_msg}",
        })
    else:
        steps.append({
            "key": "waba_subscription",
            "state": "pending",
            "detail": "WABA sin apps suscritas todavía.",
        })
        suggestions.append(
            "Asegúrate de completar la suscripción de la app al WABA antes de enviar/recibir mensajes."
        )

    phone_status = {
        "approved": False,
        "status": "UNKNOWN",
        "display_phone_number": None,
        "verified_name": None,
        "quality_rating": None,
    }

    if phone_probe is None:
        steps.append({
            "key": "phone_approval",
            "state": "pending",
            "detail": "Consultando estado del número en Meta...",
        })
    elif not bool(phone_probe.get("success")):
        detail = str(phone_probe.get("error") or "error_desconocido")
        steps.append({
            "key": "phone_approval",
            "state": "error",
            "detail": f"No se pudo leer estado del número en Meta: {detail}",
        })
        suggestions.append(
            "Revisa permisos del token y que el número exista en el mismo Business Manager."
        )
    else:
        metadata = phone_probe.get("data") or {}
        phone_status = {
            "approved": is_phone_number_approved(phone_metadata=metadata),
            "status": extract_phone_effective_status(metadata),
            "display_phone_number": metadata.get("display_phone_number"),
            "verified_name": metadata.get("verified_name"),
            "quality_rating": metadata.get("quality_rating"),
        }
        if phone_status["approved"]:
            steps.append({
                "key": "phone_approval",
                "state": "done",
                "detail": f"Número aprobado en Meta (status: {phone_status['status']}).",
            })
        else:
            steps.append({
                "key": "phone_approval",
                "state": "pending",
                "detail": f"Número aún pendiente en Meta (status: {phone_status['status']}).",
            })
            suggestions.append(
                "Si sigue pendiente, revisa verificación del número en Meta y espera unos minutos antes de reintentar."
            )

    setup_complete = bool(
        channel_ready
        and binding_ok
        and bool(subscription_probe and subscription_probe.get("success") and subscription_probe.get("subscribed"))
        and phone_status.get("approved")
    )

    return {
        "setup_complete": setup_complete,
        "steps": steps,
        "phone_status": phone_status,
        "suggestions": suggestions,
    }


def _compute_setup_progress_from_channel(channel: dict) -> dict:
    wa_phone_id = str((channel or {}).get("wa_phone_id") or "").strip()
    wa_token = str((channel or {}).get("wa_token") or "").strip()
    waba_id = str((channel or {}).get("wa_business_account_id") or "").strip()

    if not waba_id and wa_phone_id and wa_token:
        waba_id = str(resolve_waba_id_from_phone(wa_phone_id=wa_phone_id, wa_token=wa_token) or "").strip()

    channel_ready = bool(wa_phone_id and wa_token and waba_id)
    binding_ok = False
    subscription_probe = None
    phone_probe = None

    if channel_ready:
        binding_ok = validate_waba_phone_binding(
            waba_id=waba_id,
            wa_phone_id=wa_phone_id,
            wa_token=wa_token,
        )
        if binding_ok:
            subscription_probe = get_waba_subscription_status(
                waba_id=waba_id,
                wa_token=wa_token,
            )

    if wa_phone_id and wa_token:
        phone_probe = fetch_phone_number_metadata(
            wa_phone_id=wa_phone_id,
            wa_token=wa_token,
        )

    progress = _build_setup_progress(
        channel_ready=channel_ready,
        binding_ok=binding_ok,
        subscription_probe=subscription_probe,
        phone_probe=phone_probe,
    )

    return {
        "waba_id": waba_id or None,
        "binding_ok": binding_ok,
        "subscription_probe": subscription_probe,
        "phone_probe": phone_probe,
        **progress,
    }


# =====================================================
# PAYLOADS
# =====================================================

class WhatsAppLinkPayload(BaseModel):
    email: EmailStr
    phone: str
    provider: str = "meta"
    wa_phone_id: str | None = None
    wa_token: str | None = None
    wa_business_account_id: str | None = None


class WhatsAppUnlinkPayload(BaseModel):
    auth_user_id: str | None = None


class MetaEmbeddedSignupStartPayload(BaseModel):
    ui_return_url: str | None = None
    preferred_phone: str | None = None


# =====================================================
# LINK WHATSAPP
# =====================================================

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload, request: Request):
    try:
        logger.info("🔗 Linking WhatsApp channel")
        auth_user_id = get_current_user_id(request)
        client_id = get_client_id_from_user(auth_user_id)
        result = _link_whatsapp_channel_for_client(
            client_id=client_id,
            phone=payload.phone,
            provider=payload.provider,
            wa_phone_id=payload.wa_phone_id,
            wa_token=payload.wa_token,
            wa_business_account_id=payload.wa_business_account_id,
        )
        logger.info("✅ WhatsApp linked for client %s", client_id)
        return result

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ link_whatsapp internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# META EMBEDDED SIGNUP
# =====================================================

@router.post("/meta_embedded_signup/start")
def start_meta_embedded_signup(payload: MetaEmbeddedSignupStartPayload, request: Request):
    try:
        auth_user_id = get_current_user_id(request)
        client_id = get_client_id_from_user(auth_user_id)

        ui_return_url = _normalize_ui_return_url(payload.ui_return_url or _default_ui_return_url(request))
        if not _is_allowed_ui_return_url(ui_return_url):
            raise HTTPException(status_code=400, detail="ui_return_url_not_allowed")

        state = encode_signed_state(
            {
                "auth_user_id": auth_user_id,
                "client_id": client_id,
                "ui_return_url": ui_return_url,
                "preferred_phone": str(payload.preferred_phone or "").strip() or None,
            }
        )

        return {
            "success": True,
            "auth_url": _build_meta_oauth_url(request=request, state=state),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ start_meta_embedded_signup internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/meta_embedded_signup/callback", name="meta_embedded_signup_callback")
def meta_embedded_signup_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    redirect_state: str | None = None,
    error: str | None = None,
    error_reason: str | None = None,
    error_description: str | None = None,
):
    effective_state = state or redirect_state
    ui_return_url = _default_ui_return_url(request)
    try:
        state_payload = decode_signed_state(effective_state or "", max_age_seconds=1200)
        ui_return_url = _normalize_ui_return_url(
            str(state_payload.get("ui_return_url") or _default_ui_return_url(request))
        )
    except Exception:
        state_payload = {}

    if error:
        reason = str(error_description or error_reason or error or "unknown_error").strip()[:280]
        return RedirectResponse(
            url=_append_query_params(
                ui_return_url,
                {
                    "meta_setup": "error",
                    "meta_reason": reason,
                },
            ),
            status_code=302,
        )

    if not code or not effective_state:
        return RedirectResponse(
            url=_append_query_params(
                ui_return_url,
                {
                    "meta_setup": "error",
                    "meta_reason": "missing_code_or_state",
                },
            ),
            status_code=302,
        )

    try:
        decoded = decode_signed_state(effective_state, max_age_seconds=1200)
        client_id = str(decoded.get("client_id") or "").strip()
        preferred_phone = str(decoded.get("preferred_phone") or "").strip() or None
        if not client_id:
            raise HTTPException(status_code=400, detail="invalid_embedded_signup_state")

        wa_token = _exchange_meta_code_for_token(request=request, code=code)
        candidates = discover_waba_phone_candidates(wa_token=wa_token)
        chosen = _pick_candidate_phone(candidates, preferred_phone=preferred_phone)
        if not chosen:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se encontró un número de WhatsApp en la cuenta autorizada. "
                    "Verifica que el negocio tenga WABA y phone_number_id activos."
                ),
            )

        wa_phone_id = str(chosen.get("phone_id") or "").strip()
        waba_id = str(chosen.get("waba_id") or "").strip()
        display_phone = str(chosen.get("display_phone_number") or "").strip()

        phone_e164 = _normalize_to_e164(display_phone) or _normalize_to_e164(preferred_phone)
        if not phone_e164:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo normalizar el número seleccionado. "
                    "Ingresa manualmente el número en formato E.164 y vuelve a conectar."
                ),
            )

        result = _link_whatsapp_channel_for_client(
            client_id=client_id,
            phone=phone_e164,
            provider="meta",
            wa_phone_id=wa_phone_id,
            wa_token=wa_token,
            wa_business_account_id=waba_id,
        )

        return RedirectResponse(
            url=_append_query_params(
                ui_return_url,
                {
                    "meta_setup": "success",
                    "meta_connected": "1",
                    "meta_setup_complete": "1" if bool(result.get("setup_complete")) else "0",
                },
            ),
            status_code=302,
        )
    except HTTPException as exc:
        return RedirectResponse(
            url=_append_query_params(
                ui_return_url,
                {
                    "meta_setup": "error",
                    "meta_reason": str(exc.detail)[:280],
                },
            ),
            status_code=302,
        )
    except Exception as exc:
        error_type = type(exc).__name__
        logger.exception("❌ meta_embedded_signup_callback internal error | error_type=%s", error_type)
        return RedirectResponse(
            url=_append_query_params(
                ui_return_url,
                {
                    "meta_setup": "error",
                    "meta_reason": f"internal_error:{error_type}",
                },
            ),
            status_code=302,
        )


# =====================================================
# UNLINK WHATSAPP
# =====================================================

@router.post("/unlink_whatsapp")
def unlink_whatsapp(payload: WhatsAppUnlinkPayload, request: Request):
    try:
        logger.info("🛑 Unlinking WhatsApp channel")
        auth_user_id = get_current_user_id(request)

        if payload.auth_user_id and payload.auth_user_id != auth_user_id:
            raise HTTPException(status_code=403, detail="forbidden_user_mismatch")

        client_id = get_client_id_from_user(auth_user_id)
        now = datetime.utcnow().isoformat()

        update_res = supabase.table("channels") \
            .update({
                "is_active": False,
                "wa_token": None,
                "wa_phone_id": None,
                "wa_business_account_id": None,
                "archived_at": now,
                "archived_reason": "manual_disconnect",
                "last_disconnected_at": now,
                "updated_at": now
            }) \
            .eq("client_id", client_id) \
            .eq("type", "whatsapp")

        try:
            update_res = update_res.execute()
        except Exception as update_error:
            logger.warning(
                "⚠️ channels.wa_business_account_id not available yet; retrying unlink without cache field | %s",
                update_error,
            )
            update_res = supabase.table("channels") \
                .update({
                    "is_active": False,
                    "wa_token": None,
                    "wa_phone_id": None,
                    "archived_at": now,
                    "archived_reason": "manual_disconnect",
                    "last_disconnected_at": now,
                    "updated_at": now
                }) \
                .eq("client_id", client_id) \
                .eq("type", "whatsapp") \
                .execute()

        if not update_res.data:
            logger.warning(f"⚠️ No WhatsApp channel found to unlink for client {client_id}")

        logger.info(f"✅ WhatsApp unlinked for client {client_id}")

        return {
            "success": True,
            "connected": False
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ unlink_whatsapp internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# WHATSAPP SETUP PROGRESS
# =====================================================

@router.get("/whatsapp_setup_progress")
def whatsapp_setup_progress(request: Request):
    try:
        auth_user_id = get_current_user_id(request)
        client_id = get_client_id_from_user(auth_user_id)

        channel = get_active_whatsapp_channel(client_id)
        if not channel:
            progress = _build_setup_progress(
                channel_ready=False,
                binding_ok=False,
                subscription_probe=None,
                phone_probe=None,
            )
            return {
                "success": True,
                "connected": False,
                "setup_complete": False,
                **progress,
                "poll_after_seconds": 5,
            }

        progress = _compute_setup_progress_from_channel(channel)
        return {
            "success": True,
            "connected": True,
            "setup_complete": bool(progress.get("setup_complete")),
            "waba_id": progress.get("waba_id"),
            "steps": progress.get("steps"),
            "phone_status": progress.get("phone_status"),
            "suggestions": progress.get("suggestions"),
            "poll_after_seconds": 5,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ whatsapp_setup_progress internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# STATUS (SAFE — never returns token)
# =====================================================

@router.get("/whatsapp_status")
def whatsapp_status(request: Request):
    try:
        auth_user_id = get_current_user_id(request)
        client_id = get_client_id_from_user(auth_user_id)

        try:
            channel_res = (
                supabase.table("channels")
                .select("value, provider, wa_phone_id, wa_business_account_id")
                .eq("client_id", client_id)
                .eq("type", "whatsapp")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
        except Exception:
            channel_res = (
                supabase.table("channels")
                .select("value, provider, wa_phone_id")
                .eq("client_id", client_id)
                .eq("type", "whatsapp")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )

        if channel_res.data:
            return {
                "connected": True,
                "phone": channel_res.data[0]["value"],
                "provider": channel_res.data[0]["provider"],
                "wa_phone_id": channel_res.data[0]["wa_phone_id"],
                "wa_business_account_id": channel_res.data[0].get("wa_business_account_id"),
            }

        return {"connected": False}

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ whatsapp_status internal error")
        raise HTTPException(status_code=500, detail="Internal server error")
