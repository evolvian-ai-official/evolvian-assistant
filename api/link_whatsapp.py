from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.template_sync import (
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
from api.authz import get_current_user_id

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


# =====================================================
# LINK WHATSAPP
# =====================================================

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload, request: Request):
    try:
        logger.info("🔗 Linking WhatsApp channel")
        auth_user_id = get_current_user_id(request)

        # 1️⃣ Validate provider
        if payload.provider not in ["meta", "twilio"]:
            raise HTTPException(status_code=400, detail="Proveedor inválido")

        if payload.provider == "meta":
            if not payload.wa_phone_id or not payload.wa_token:
                raise HTTPException(
                    status_code=400,
                    detail="Meta requiere wa_phone_id y wa_token"
                )

        # 2️⃣ Secure client lookup
        client_id = get_client_id_from_user(auth_user_id)

        # 3️⃣ Validate phone
        number = validate_e164(payload.phone)
        now = datetime.utcnow().isoformat()
        resolved_waba_id = None
        waba_subscription = None
        phone_probe = None
        setup_progress = None

        # 4️⃣ Resolve or accept provided WABA id
        if payload.provider == "meta":
            provided_waba_id = str(payload.wa_business_account_id or "").strip()
            if provided_waba_id:
                if not re.match(r"^\d{8,24}$", provided_waba_id):
                    raise HTTPException(status_code=400, detail="wa_business_account_id inválido")
                resolved_waba_id = provided_waba_id
            else:
                resolved_waba_id = resolve_waba_id_from_phone(
                    wa_phone_id=str(payload.wa_phone_id or ""),
                    wa_token=str(payload.wa_token or ""),
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
                wa_phone_id=str(payload.wa_phone_id or ""),
                wa_token=str(payload.wa_token or ""),
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
                wa_token=str(payload.wa_token or ""),
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
                wa_phone_id=str(payload.wa_phone_id or ""),
                wa_token=str(payload.wa_token or ""),
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
        if payload.provider == "meta":
            try:
                encrypted_wa_token = encrypt_whatsapp_token(str(payload.wa_token or ""))
            except ValueError:
                raise HTTPException(status_code=400, detail="Meta requiere wa_token válido")
            except RuntimeError as crypto_error:
                raise HTTPException(status_code=500, detail=str(crypto_error))

        # 5️⃣ Deactivate previous WhatsApp channel
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

        # 6️⃣ Insert new channel
        insert_payload = {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "type": "whatsapp",
            "value": number,
            "provider": payload.provider,
            "wa_phone_id": payload.wa_phone_id,
            "wa_token": encrypted_wa_token,  # encrypted at rest
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

        # 7️⃣ Sync templates (no rompe si falla)
        sync_summary = None
        if payload.provider == "meta":
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

        logger.info(f"✅ WhatsApp linked for client {client_id}")

        return {
            "success": True,
            "connected": True,
            "waba_subscription": waba_subscription,
            "phone_probe": phone_probe,
            "setup_complete": bool((setup_progress or {}).get("setup_complete")),
            "setup_progress": setup_progress,
            "template_sync": sync_summary,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ link_whatsapp internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


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
