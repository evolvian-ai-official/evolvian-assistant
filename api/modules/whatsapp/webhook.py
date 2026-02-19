from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
import os
import json
import logging
import re
from datetime import datetime, timezone

from api.modules.assistant_rag.rag_pipeline import handle_message
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message
from api.config.config import supabase
from api.modules.assistant_rag.supabase_client import (
    get_channel_by_wa_phone_id,
    is_duplicate_wa_message,
    register_wa_message,
)
from api.webhook_security import verify_meta_signature

router = APIRouter(prefix="/api/whatsapp")
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "evolvian2025")
if VERIFY_TOKEN == "evolvian2025":
    logger.warning("⚠️ Using default META_WHATSAPP_VERIFY_TOKEN. Configure env var in production.")

CANCEL_KEYWORDS = ("cancelar", "cancel", "anular", "cancelacion", "cancelación")


def _extract_user_text(message_type: str, message: dict) -> str | None:
    if message_type == "text":
        return message.get("text", {}).get("body")

    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        button = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}
        return (
            button.get("title")
            or button.get("id")
            or list_reply.get("title")
            or list_reply.get("id")
        )

    # Meta template quick-reply button callbacks llegan como type="button".
    if message_type == "button":
        button = message.get("button") or {}
        return button.get("text") or button.get("payload")

    return None


def _phone_candidates(from_number: str) -> list[str]:
    digits = re.sub(r"\D", "", from_number or "")
    if not digits:
        return []

    candidates = {
        digits,
        f"+{digits}",
    }

    # Compatibilidad MX (algunos proveedores reportan 521..., otros 52...)
    if digits.startswith("521") and len(digits) > 3:
        mx_alt = f"52{digits[3:]}"
        candidates.add(mx_alt)
        candidates.add(f"+{mx_alt}")

    if digits.startswith("52") and len(digits) > 2:
        mx_alt = f"521{digits[2:]}"
        candidates.add(mx_alt)
        candidates.add(f"+{mx_alt}")

    # Orden estable para facilitar debugging
    return sorted(candidates, key=lambda x: (len(x), x))


def _is_cancel_action(message_type: str, message: dict, user_text: str | None) -> bool:
    text = (user_text or "").strip().lower()

    if message_type == "button":
        button = message.get("button") or {}
        combined = " ".join([
            str(button.get("text") or ""),
            str(button.get("payload") or ""),
        ]).lower()
        return any(keyword in combined for keyword in CANCEL_KEYWORDS)

    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        button = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}

        combined = " ".join([
            str(button.get("id") or ""),
            str(button.get("title") or ""),
            str(list_reply.get("id") or ""),
            str(list_reply.get("title") or ""),
        ]).lower()

        return any(keyword in combined for keyword in CANCEL_KEYWORDS)

    return text in {"cancelar", "cancel"}


def _find_next_active_appointment(client_id: str, from_number: str) -> dict | None:
    now_iso = datetime.now(timezone.utc).isoformat()
    candidates = _phone_candidates(from_number)
    if not candidates:
        return None

    best_match = None

    for phone in candidates:
        try:
            res = (
                supabase
                .table("appointments")
                .select("id, scheduled_time, status, user_phone")
                .eq("client_id", client_id)
                .in_("status", ["confirmed", "pending_confirmation"])
                .eq("user_phone", phone)
                .gte("scheduled_time", now_iso)
                .order("scheduled_time", desc=False)
                .limit(1)
                .execute()
            )
        except Exception:
            continue

        row = (res.data or [None])[0]
        if not row:
            continue

        if (
            not best_match
            or (row.get("scheduled_time") or "") < (best_match.get("scheduled_time") or "")
        ):
            best_match = row

    return best_match


def _cancel_appointment_from_whatsapp(client_id: str, from_number: str) -> tuple[bool, str]:
    appointment = _find_next_active_appointment(client_id, from_number)
    if not appointment:
        return False, "ℹ️ No encontré una cita activa para cancelar."

    appointment_id = appointment["id"]
    now_iso = datetime.utcnow().isoformat()

    supabase.table("appointments").update({
        "status": "cancelled",
        "updated_at": now_iso,
    }).eq("id", appointment_id).eq("client_id", client_id).execute()

    supabase.table("appointment_reminders").update({
        "status": "cancelled",
        "updated_at": now_iso,
    }).eq("appointment_id", appointment_id).eq("client_id", client_id).in_(
        "status",
        ["pending", "processing", "sending"]
    ).execute()

    supabase.table("appointment_usage").insert({
        "client_id": client_id,
        "appointment_id": appointment_id,
        "channel": "whatsapp",
        "action": "cancelled_from_whatsapp_button",
        "created_at": now_iso,
    }).execute()

    return True, "✅ Tu cita fue cancelada."


# -------------------------------------------------------------------
# 🔐 Webhook verification (Meta GET)
# -------------------------------------------------------------------
@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ WhatsApp Webhook Verified")
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# -------------------------------------------------------------------
# 📩 Incoming WhatsApp messages (Meta POST)
# -------------------------------------------------------------------
@router.post("/webhook")
async def incoming_message(
    request: Request,
    background_tasks: BackgroundTasks
):
    print("🚀🚀🚀 WHATSAPP WEBHOOK HIT 🚀🚀🚀")

    try:
        raw_body = await request.body()
        verify_meta_signature(request, raw_body)
        payload = json.loads(raw_body.decode("utf-8") or "{}")

        # 🔴 CRÍTICO
        # Respondemos 200 INMEDIATO a Meta para evitar retries
        background_tasks.add_task(process_whatsapp_payload, payload)

        return {"received": True}

    except HTTPException:
        raise
    except Exception as e:
        # ⚠️ JAMÁS devolver 4xx/5xx a Meta por errores internos
        # o entrará en retry infinito
        print("❌ WhatsApp webhook parse error:", str(e))
        return {"received": True}


# -------------------------------------------------------------------
# 🧠 Background processor (NO bloquea webhook)
# -------------------------------------------------------------------
async def process_whatsapp_payload(payload: dict):
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})

        # -------------------------------------------------------------
        # 🛑 Ignorar callbacks de estado (sent, delivered, read)
        # -------------------------------------------------------------
        if "statuses" in value:
            print("ℹ️ Status callback ignored")
            return

        messages = value.get("messages")
        if not messages:
            return

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        if not phone_number_id:
            return

        # -------------------------------------------------------------
        # Procesar TODOS los mensajes (Meta puede mandar batch)
        # -------------------------------------------------------------
        for message in messages:
            message_type = message.get("type")
            if message_type not in {"text", "interactive", "button"}:
                continue

            wa_message_id = message.get("id")
            from_number = message.get("from")

            user_text = _extract_user_text(message_type, message)

            if not wa_message_id or not from_number or not user_text:
                continue

            print(f"📩 Incoming WA message [{message_type}]:", wa_message_id, user_text)

            # ---------------------------------------------------------
            # Resolver canal / cliente (MULTITENANT)
            # ---------------------------------------------------------
            channel = get_channel_by_wa_phone_id(phone_number_id)
            if not channel:
                print("⚠️ Unknown channel")
                continue

            client_id = channel.get("client_id")
            if not client_id:
                print("⚠️ Channel without client_id")
                continue

            # ---------------------------------------------------------
            # 🛑 DEDUPE CRÍTICO (idempotency por wamid)
            # ---------------------------------------------------------
            if is_duplicate_wa_message(wa_message_id):
                print("🔁 Duplicate message ignored:", wa_message_id)
                continue

            # Registrar inmediatamente para bloquear retries
            register_wa_message(
                wa_message_id=wa_message_id,
                client_id=client_id,
                from_number=from_number,
            )

            session_id = f"whatsapp-{from_number}"

            # ---------------------------------------------------------
            # Cancelación directa desde botón rápido
            # ---------------------------------------------------------
            if _is_cancel_action(message_type, message, user_text):
                try:
                    cancelled, cancel_msg = _cancel_appointment_from_whatsapp(
                        client_id=client_id,
                        from_number=from_number,
                    )
                    logger.info(
                        "🧾 WhatsApp cancel action | client_id=%s | from=%s | cancelled=%s",
                        client_id,
                        from_number,
                        cancelled,
                    )
                except Exception:
                    logger.exception(
                        "❌ WhatsApp cancel action failed | client_id=%s | from=%s",
                        client_id,
                        from_number,
                    )
                    cancel_msg = "⚠️ No pude cancelar tu cita en este momento. Intenta de nuevo."

                await send_whatsapp_message(
                    to_number=from_number,
                    text=cancel_msg,
                    channel=channel,
                )
                continue

            # ---------------------------------------------------------
            # Ejecutar RAG
            # ---------------------------------------------------------
            assistant_response = await handle_message(
                client_id=client_id,
                session_id=session_id,
                user_message=user_text,
                channel="whatsapp",
                provider="meta",
            )

            # ---------------------------------------------------------
            # Enviar respuesta SOLO una vez
            # ---------------------------------------------------------
            await send_whatsapp_message(
                to_number=from_number,
                text=assistant_response,
                channel=channel,
            )

            print("✅ WhatsApp message processed:", wa_message_id)

    except Exception as e:
        # ⚠️ Nunca levantar excepción aquí
        # Meta YA recibió 200 OK
        print("❌ WhatsApp background error:", str(e))
