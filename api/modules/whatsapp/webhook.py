from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
import os
import json
import logging
import re
import hashlib
import uuid
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from api.modules.assistant_rag.rag_pipeline import handle_message
from api.modules.whatsapp.whatsapp_sender import send_whatsapp_message
from api.config.config import supabase
from api.marketing_contacts_state import upsert_marketing_contact_state
from api.appointments.cancellation_notifications import (
    send_appointment_cancellation_notification,
    send_appointment_cancellation_email_notification,
)
from api.modules.assistant_rag.supabase_client import (
    get_channel_by_wa_phone_id,
    is_duplicate_wa_message,
    register_wa_message,
)
from api.privacy_dsr import (
    build_initial_metadata,
    calculate_due_at,
    combine_details_and_metadata,
    isoformat_utc,
    now_utc,
    split_details_and_metadata,
)
from api.webhook_security import verify_meta_signature

router = APIRouter(prefix="/api/whatsapp")
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "evolvian2025")
if VERIFY_TOKEN == "evolvian2025":
    VERIFY_TOKEN = ""
if not VERIFY_TOKEN:
    if os.getenv("ENV") == "prod":
        logger.error("META_WHATSAPP_VERIFY_TOKEN is not configured.")
    else:
        logger.warning("META_WHATSAPP_VERIFY_TOKEN is not configured (dev mode).")

CANCEL_KEYWORDS = ("cancelar", "cancel", "anular", "cancelacion", "cancelación")
TERMINAL_OPT_OUT_STATUSES = {"withdrawn", "denied"}
OPT_OUT_KEYWORDS = (
    "stop",
    "unsubscribe",
    "optout",
    "opt out",
    "desuscribir",
    "desuscribirme",
    "darme de baja",
    "no recibir",
    "no mas",
    "no más",
)
INTEREST_KEYWORDS = (
    "me interesa",
    "estoy interesado",
    "estoy interesada",
    "quiero info",
    "quiero informacion",
    "quiero información",
    "quiero saber mas",
    "quiero saber más",
    "interested",
    "i'm interested",
    "im interested",
    "tell me more",
    "more info",
)


def _safe_hash(value: Any, *, length: int = 12) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "na"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _safe_tail(value: Any, *, size: int = 8) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "na"
    return raw[-size:]


def _normalize_whatsapp_session_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return str(value or "").strip()
    # Normalize MX mobile variant so one user does not split conversation state
    # across 521XXXXXXXXXX and 52XXXXXXXXXX session ids.
    if digits.startswith("521") and len(digits) > 3:
        digits = f"52{digits[3:]}"
    return f"+{digits}"


def _normalize_text_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_context_message_id(message: dict) -> str | None:
    context = message.get("context")
    if not isinstance(context, dict):
        return None
    value = str(context.get("id") or "").strip()
    return value or None


def _extract_email_from_recipient_key(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower().startswith("email:"):
        email = text.split(":", 1)[1].strip().lower()
        return email or None
    return None


def _extract_opt_out_scope_client_id(details: Any) -> Optional[str]:
    try:
        plain_details, metadata = split_details_and_metadata(str(details or ""))
        scoped = str((metadata or {}).get("client_id") or "").strip()
        if scoped:
            return scoped
        match = re.search(r"\bclient_id=([a-f0-9-]{8,})\b", plain_details, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip()
    except Exception:
        return None
    return None


def _load_recent_marketing_recipient(
    *,
    client_id: str,
    from_number: str,
    context_message_id: Optional[str],
) -> Optional[dict]:
    if context_message_id:
        try:
            scoped = (
                supabase.table("marketing_campaign_recipients")
                .select("campaign_id,recipient_key,email,phone,provider_message_id,sent_at,updated_at")
                .eq("client_id", client_id)
                .eq("provider", "meta")
                .eq("provider_message_id", context_message_id)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            row = (scoped.data or [None])[0]
            if row:
                return row
            # If Meta sent an explicit context id, avoid stale phone-based fallback.
            return None
        except Exception:
            return None

    phone_candidates = _phone_candidates(from_number)
    if not phone_candidates:
        return None
    try:
        by_phone = (
            supabase.table("marketing_campaign_recipients")
            .select("campaign_id,recipient_key,email,phone,provider_message_id,sent_at,updated_at")
            .eq("client_id", client_id)
            .eq("provider", "meta")
            .in_("phone", phone_candidates)
            .order("updated_at", desc=True)
            .limit(5)
            .execute()
        )
        return (by_phone.data or [None])[0]
    except Exception:
        return None


def _load_campaign_opt_out_labels(client_id: str, campaign_id: Optional[str]) -> set[str]:
    normalized_campaign_id = str(campaign_id or "").strip()
    if not normalized_campaign_id:
        return set()

    try:
        campaign_res = (
            supabase.table("marketing_campaigns")
            .select("meta_template_id")
            .eq("id", normalized_campaign_id)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        campaign_row = (campaign_res.data or [None])[0] or {}
        meta_template_id = str(campaign_row.get("meta_template_id") or "").strip()
        if not meta_template_id:
            return set()

        meta_res = (
            supabase.table("meta_approved_templates")
            .select("buttons_json")
            .eq("id", meta_template_id)
            .limit(1)
            .execute()
        )
        meta_row = (meta_res.data or [None])[0] or {}
        raw = meta_row.get("buttons_json")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = None
        if isinstance(raw, list):
            raw = {"buttons": raw}
        if not isinstance(raw, dict):
            return set()
        buttons = raw.get("buttons")
        if not isinstance(buttons, list):
            return set()

        labels: set[str] = set()
        has_explicit_button_purpose = False
        quick_reply_labels: list[str] = []
        for button in buttons:
            if not isinstance(button, dict):
                continue
            if str(button.get("type") or "").strip().upper() != "QUICK_REPLY":
                continue
            label = _normalize_text_key(button.get("text"))
            if not label:
                continue
            quick_reply_labels.append(label)
            purpose = _normalize_text_key(button.get("purpose"))
            if purpose:
                has_explicit_button_purpose = True
            if purpose == "opt_out":
                labels.add(label)
                continue
            if not purpose and any(keyword in label for keyword in OPT_OUT_KEYWORDS):
                labels.add(label)
        if labels:
            return labels
        if len(quick_reply_labels) == 1 and not has_explicit_button_purpose:
            # Legacy campaigns used one quick reply and it represented opt-out.
            return {quick_reply_labels[0]}
        return labels
    except Exception:
        return set()


def _is_marketing_opt_out_action(
    *,
    message_type: str,
    user_text: Optional[str],
    known_opt_out_labels: set[str],
) -> bool:
    normalized_text = _normalize_text_key(user_text)
    if not normalized_text:
        return False

    is_button_like = message_type in {"interactive", "button"}
    if is_button_like and normalized_text in known_opt_out_labels:
        return True

    return any(keyword in normalized_text for keyword in OPT_OUT_KEYWORDS)


def _is_marketing_interest_action(
    *,
    message_type: str,
    user_text: Optional[str],
    known_opt_out_labels: set[str],
) -> bool:
    normalized_text = _normalize_text_key(user_text)

    # Any marketing button click should open a human handoff unless it is an opt-out label.
    if message_type in {"interactive", "button"}:
        # Reservation cancellation buttons must go through appointment cancellation flow.
        if normalized_text and any(keyword in normalized_text for keyword in CANCEL_KEYWORDS):
            return False
        if normalized_text and normalized_text in known_opt_out_labels:
            return False
        return True

    if not normalized_text:
        return False
    if normalized_text in known_opt_out_labels:
        return False

    return any(keyword in normalized_text for keyword in INTEREST_KEYWORDS)


def _resolve_interest_language(user_text: Optional[str]) -> str:
    text = _normalize_text_key(user_text)
    if not text:
        return "es"
    en_signals = ("interested", "tell me more", "more info", "i'm", "im ")
    return "en" if any(signal in text for signal in en_signals) else "es"


def _record_whatsapp_marketing_opt_out(
    *,
    client_id: str,
    email: str,
    campaign_id: Optional[str],
    provider_message_id: Optional[str],
    recipient_key: Optional[str],
) -> bool:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return False

    try:
        existing = (
            supabase.table("public_privacy_requests")
            .select("id,status,created_at,details")
            .eq("email", normalized_email)
            .eq("request_type", "marketing_opt_out")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = existing.data or []
    except Exception:
        rows = []

    latest_for_client = None
    for row in rows:
        scoped_client_id = _extract_opt_out_scope_client_id((row or {}).get("details"))
        if scoped_client_id and str(scoped_client_id) != str(client_id):
            continue
        latest_for_client = row or {}
        break

    status = str((latest_for_client or {}).get("status") or "").strip().lower()
    has_active_opt_out = bool(latest_for_client) and status not in TERMINAL_OPT_OUT_STATUSES
    if has_active_opt_out:
        return True

    submitted_at = now_utc()
    due_at = calculate_due_at(submitted_at)
    request_id = f"dsar_{uuid.uuid4().hex[:12]}"
    metadata = build_initial_metadata(
        request_id=request_id,
        request_type="marketing_opt_out",
        submitted_at=submitted_at,
        due_at=due_at,
        source="whatsapp_campaign_button",
    )
    metadata["client_id"] = str(client_id).strip()
    if campaign_id:
        metadata["campaign_id"] = str(campaign_id).strip()
    if provider_message_id:
        metadata["provider_message_id"] = str(provider_message_id).strip()
    if recipient_key:
        metadata["recipient_key"] = str(recipient_key).strip()

    details = "Marketing opt-out via WhatsApp campaign button."
    details_with_metadata = combine_details_and_metadata(details, metadata)
    payload = {
        "name": None,
        "email": normalized_email,
        "request_type": "marketing_opt_out",
        "details": details_with_metadata,
        "language": "es",
        "consent_version": "2026-02",
        "source": "whatsapp_campaign_button",
        "status": "pending",
        "ip_address": None,
        "user_agent": "meta_whatsapp_webhook",
        "created_at": isoformat_utc(submitted_at),
    }
    supabase.table("public_privacy_requests").insert(payload).execute()
    return True


def _log_marketing_opt_out_event(
    *,
    client_id: str,
    campaign_id: Optional[str],
    recipient_key: Optional[str],
    provider_message_id: Optional[str],
) -> None:
    normalized_campaign_id = str(campaign_id or "").strip()
    normalized_recipient_key = str(recipient_key or "").strip()
    if not normalized_campaign_id:
        return
    try:
        supabase.table("marketing_campaign_events").insert(
            {
                "client_id": client_id,
                "campaign_id": normalized_campaign_id,
                "recipient_key": normalized_recipient_key or None,
                "event_type": "opt_out",
                "metadata": {"provider_message_id": provider_message_id} if provider_message_id else {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        logger.exception(
            "❌ Failed logging marketing opt-out event | client_id=%s | campaign_id=%s",
            client_id,
            normalized_campaign_id,
        )


def _log_marketing_interest_event(
    *,
    client_id: str,
    campaign_id: Optional[str],
    recipient_key: Optional[str],
    provider_message_id: Optional[str],
    handoff_id: Optional[str],
) -> None:
    normalized_campaign_id = str(campaign_id or "").strip()
    normalized_recipient_key = str(recipient_key or "").strip()
    if not normalized_campaign_id:
        return
    metadata: dict[str, Any] = {}
    if provider_message_id:
        metadata["provider_message_id"] = provider_message_id
    if handoff_id:
        metadata["handoff_id"] = handoff_id
    try:
        supabase.table("marketing_campaign_events").insert(
            {
                "client_id": client_id,
                "campaign_id": normalized_campaign_id,
                "recipient_key": normalized_recipient_key or None,
                "event_type": "interest_yes",
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        logger.exception(
            "❌ Failed logging marketing interest event | client_id=%s | campaign_id=%s",
            client_id,
            normalized_campaign_id,
        )


def _compact_meta_status_error(status_item: dict) -> Optional[str]:
    errors = status_item.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0] if isinstance(errors[0], dict) else {}
    code = str(first.get("code") or "").strip()
    title = str(first.get("title") or "").strip()
    message = str(first.get("message") or "").strip()
    parts = [part for part in [code, title, message] if part]
    return " | ".join(parts) if parts else None


def _sync_marketing_status_from_meta_callback(status_item: dict) -> None:
    provider_message_id = str(status_item.get("id") or "").strip()
    if not provider_message_id:
        return

    callback_status = str(status_item.get("status") or "").strip().lower() or "unknown"
    error_text = _compact_meta_status_error(status_item)
    updated_at = datetime.now(timezone.utc).isoformat()
    mapped_send_status = "failed" if callback_status in {"failed", "undelivered"} else None

    try:
        rows = (
            supabase.table("marketing_campaign_recipients")
            .select("id,client_id,campaign_id,recipient_key")
            .eq("provider", "meta")
            .eq("provider_message_id", provider_message_id)
            .limit(50)
            .execute()
        ).data or []
    except Exception:
        logger.exception(
            "❌ Failed loading marketing recipients for Meta status callback | message_id=%s",
            provider_message_id,
        )
        return

    for row in rows:
        recipient_id = str((row or {}).get("id") or "").strip()
        if not recipient_id:
            continue
        try:
            update_payload = {
                "updated_at": updated_at,
            }
            if mapped_send_status:
                update_payload["send_status"] = mapped_send_status
                update_payload["send_error"] = error_text or f"meta_status:{callback_status}"

            (
                supabase.table("marketing_campaign_recipients")
                .update(update_payload)
                .eq("id", recipient_id)
                .execute()
            )
        except Exception:
            logger.exception(
                "❌ Failed updating marketing recipient from Meta status callback | recipient_id=%s",
                recipient_id,
            )

        try:
            supabase.table("marketing_campaign_events").insert(
                {
                    "client_id": row.get("client_id"),
                    "campaign_id": row.get("campaign_id"),
                    "recipient_key": row.get("recipient_key"),
                    "event_type": f"meta_{callback_status}",
                    "metadata": {
                        "provider_message_id": provider_message_id,
                        "callback_status": callback_status,
                        "error": error_text,
                    },
                    "created_at": updated_at,
                }
            ).execute()
        except Exception:
            logger.exception(
                "❌ Failed writing marketing event from Meta status callback | message_id=%s",
                provider_message_id,
            )


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
                .select("id, scheduled_time, status, user_phone, user_name, user_email, appointment_type")
                .eq("client_id", client_id)
                .in_("status", ["confirmed", "pending_confirmation", "pending"])
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


async def _cancel_appointment_from_whatsapp(client_id: str, from_number: str) -> tuple[bool, str]:
    appointment = _find_next_active_appointment(client_id, from_number)
    if not appointment:
        return False, "ℹ️ No encontré una cita activa para cancelar."

    appointment_id = appointment["id"]
    now_iso = datetime.utcnow().isoformat()

    update_res = (
        supabase
        .table("appointments")
        .update({
            "status": "cancelled",
            "updated_at": now_iso,
        })
        .eq("id", appointment_id)
        .eq("client_id", client_id)
        .execute()
    )

    verify_res = (
        supabase
        .table("appointments")
        .select("id, status")
        .eq("id", appointment_id)
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )

    updated_row = verify_res.data or {}
    if updated_row.get("status") != "cancelled":
        logger.error(
            "❌ WhatsApp cancel did not persist | client_id=%s | appointment_id=%s | update_data=%s | verify_data=%s",
            client_id,
            appointment_id,
            update_res.data,
            verify_res.data,
        )
        return False, "⚠️ No pude confirmar la cancelación en el sistema. Intenta de nuevo."

    try:
        supabase.table("appointment_reminders").update({
            "status": "cancelled",
            "updated_at": now_iso,
        }).eq("appointment_id", appointment_id).eq("client_id", client_id).in_(
            "status",
            ["pending", "processing", "sending"]
        ).execute()
    except Exception:
        logger.exception(
            "❌ Failed cancelling reminders from WhatsApp | client_id=%s | appointment_id=%s",
            client_id,
            appointment_id,
        )

    try:
        supabase.table("appointment_usage").insert({
            "client_id": client_id,
            "appointment_id": appointment_id,
            "channel": "whatsapp",
            "action": "cancelled_from_whatsapp_button",
            "created_at": now_iso,
        }).execute()
    except Exception:
        logger.exception(
            "❌ Failed logging WhatsApp cancellation usage | client_id=%s | appointment_id=%s",
            client_id,
            appointment_id,
        )

    logger.info(
        "✅ WhatsApp appointment cancelled | client_ref=%s | appointment_ref=%s | user_phone_fp=%s",
        _safe_tail(client_id),
        _safe_tail(appointment_id),
        _safe_hash(appointment.get("user_phone")),
    )

    logger.info(
        "WhatsApp cancellation persisted | client_ref=%s | appointment_ref=%s",
        _safe_tail(client_id),
        _safe_tail(appointment_id),
    )

    notification_sent = False
    try:
        notification_sent = await send_appointment_cancellation_notification({
            "id": appointment_id,
            "client_id": client_id,
            "user_name": appointment.get("user_name"),
            "user_email": appointment.get("user_email"),
            "user_phone": appointment.get("user_phone"),
            "scheduled_time": appointment.get("scheduled_time"),
        })
    except Exception:
        logger.exception(
            "❌ Cancellation template send crashed from WhatsApp flow | client_id=%s | appointment_id=%s",
            client_id,
            appointment_id,
        )

    try:
        send_appointment_cancellation_email_notification({
            "id": appointment_id,
            "client_id": client_id,
            "user_name": appointment.get("user_name"),
            "user_email": appointment.get("user_email"),
            "user_phone": appointment.get("user_phone"),
            "scheduled_time": appointment.get("scheduled_time"),
            "appointment_type": appointment.get("appointment_type"),
        })
    except Exception:
        logger.exception(
            "❌ Cancellation email send crashed from WhatsApp flow | client_id=%s | appointment_id=%s",
            client_id,
            appointment_id,
        )

    if notification_sent:
        # Template already sent as WhatsApp message; avoid duplicate text acknowledgment.
        return True, ""

    return True, "✅ Tu cita fue cancelada."


# -------------------------------------------------------------------
# 🔐 Webhook verification (Meta GET)
# -------------------------------------------------------------------
@router.get("/webhook")
async def verify_webhook(request: Request):
    if not VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail="Webhook verify token is not configured")

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
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
    try:
        raw_body = await request.body()
        verify_meta_signature(request, raw_body)
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        entry_count = len(payload.get("entry") or []) if isinstance(payload, dict) else 0
        logger.info(
            "Incoming WhatsApp webhook accepted | body_bytes=%s | entry_count=%s",
            len(raw_body or b""),
            entry_count,
        )

        # 🔴 CRÍTICO
        # Respondemos 200 INMEDIATO a Meta para evitar retries
        background_tasks.add_task(process_whatsapp_payload, payload)

        return {"received": True}

    except HTTPException:
        raise
    except Exception as e:
        # ⚠️ JAMÁS devolver 4xx/5xx a Meta por errores internos
        # o entrará en retry infinito
        logger.exception("WhatsApp webhook parse error")
        return {"received": True}


# -------------------------------------------------------------------
# 🧠 Background processor (NO bloquea webhook)
# -------------------------------------------------------------------
async def process_whatsapp_payload(payload: dict):
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})
        logger.info(
            "Meta payload parsed | has_statuses=%s | has_messages=%s | metadata_phone_id_fp=%s",
            bool(value.get("statuses")),
            bool(value.get("messages")),
            _safe_hash((value.get("metadata") or {}).get("phone_number_id")),
        )

        # -------------------------------------------------------------
        # 🛑 Ignorar callbacks de estado (sent, delivered, read)
        # -------------------------------------------------------------
        if "statuses" in value:
            statuses = value.get("statuses") or []
            for status_item in statuses:
                if not isinstance(status_item, dict):
                    continue
                provider_message_id = str(status_item.get("id") or "").strip() or "unknown"
                callback_status = str(status_item.get("status") or "").strip().lower() or "unknown"
                recipient_id = str(status_item.get("recipient_id") or "").strip() or "unknown"
                error_text = _compact_meta_status_error(status_item)
                logger.info(
                    "WhatsApp status callback | message_fp=%s | status=%s | recipient_fp=%s | error=%s",
                    _safe_hash(provider_message_id),
                    callback_status,
                    _safe_hash(recipient_id),
                    error_text or "none",
                )
                _sync_marketing_status_from_meta_callback(status_item)
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

            if not wa_message_id or not from_number:
                continue
            if not user_text:
                if message_type in {"interactive", "button"}:
                    user_text = "button_click"
                else:
                    continue

            # ---------------------------------------------------------
            # Resolver canal / cliente (MULTITENANT)
            # ---------------------------------------------------------
            channel = get_channel_by_wa_phone_id(phone_number_id)
            if not channel:
                logger.warning("Unknown WhatsApp channel for phone_number_id_fp=%s", _safe_hash(phone_number_id))
                continue

            client_id = channel.get("client_id")
            if not client_id:
                logger.warning("WhatsApp channel without client_id | phone_number_id_fp=%s", _safe_hash(phone_number_id))
                continue

            # ---------------------------------------------------------
            # 🛑 DEDUPE CRÍTICO (idempotency por wamid)
            # ---------------------------------------------------------
            if is_duplicate_wa_message(wa_message_id):
                logger.info("Duplicate WhatsApp message ignored | message_fp=%s", _safe_hash(wa_message_id))
                continue

            # Registrar inmediatamente para bloquear retries
            register_wa_message(
                wa_message_id=wa_message_id,
                client_id=client_id,
                from_number=from_number,
            )

            normalized_session_phone = _normalize_whatsapp_session_phone(from_number) or from_number
            session_id = f"whatsapp-{normalized_session_phone}"
            context_message_id = _extract_context_message_id(message)
            logger.info(
                "Meta inbound message | type=%s | message_fp=%s | from_fp=%s | session_fp=%s | context_fp=%s | text_len=%s",
                message_type,
                _safe_hash(wa_message_id),
                _safe_hash(from_number),
                _safe_hash(session_id),
                _safe_hash(context_message_id),
                len(str(user_text or "")),
            )

            recent_marketing_row = _load_recent_marketing_recipient(
                client_id=client_id,
                from_number=from_number,
                context_message_id=context_message_id,
            )
            logger.info(
                "Meta marketing context resolved | message_fp=%s | has_recent_campaign=%s | campaign_ref=%s",
                _safe_hash(wa_message_id),
                bool(recent_marketing_row),
                _safe_tail((recent_marketing_row or {}).get("campaign_id")),
            )
            known_opt_out_labels = _load_campaign_opt_out_labels(
                client_id=client_id,
                campaign_id=(recent_marketing_row or {}).get("campaign_id"),
            )
            is_opt_out_candidate = bool(recent_marketing_row) or message_type in {"interactive", "button"}
            if is_opt_out_candidate and _is_marketing_opt_out_action(
                message_type=message_type,
                user_text=user_text,
                known_opt_out_labels=known_opt_out_labels,
            ):
                recipient_email = str((recent_marketing_row or {}).get("email") or "").strip().lower()
                if not recipient_email:
                    recipient_email = (
                        _extract_email_from_recipient_key((recent_marketing_row or {}).get("recipient_key"))
                        or ""
                    )

                if recipient_email:
                    _record_whatsapp_marketing_opt_out(
                        client_id=client_id,
                        email=recipient_email,
                        campaign_id=(recent_marketing_row or {}).get("campaign_id"),
                        provider_message_id=context_message_id or (recent_marketing_row or {}).get("provider_message_id"),
                        recipient_key=(recent_marketing_row or {}).get("recipient_key"),
                    )
                    _log_marketing_opt_out_event(
                        client_id=client_id,
                        campaign_id=(recent_marketing_row or {}).get("campaign_id"),
                        recipient_key=(recent_marketing_row or {}).get("recipient_key"),
                        provider_message_id=context_message_id or (recent_marketing_row or {}).get("provider_message_id"),
                    )
                    upsert_marketing_contact_state(
                        supabase_client=supabase,
                        client_id=client_id,
                        email=recipient_email,
                        phone=(recent_marketing_row or {}).get("phone"),
                        whatsapp_unsubscribed=True,
                    )
                    logger.info(
                        "Meta opt-out processed | message_fp=%s | campaign_ref=%s | email_fp=%s",
                        _safe_hash(wa_message_id),
                        _safe_tail((recent_marketing_row or {}).get("campaign_id")),
                        _safe_hash(recipient_email),
                    )
                    await send_whatsapp_message(
                        to_number=from_number,
                        text="Listo. Dejaste de recibir campañas de marketing.",
                        channel=channel,
                    )
                else:
                    logger.info(
                        "Meta opt-out missing email | message_fp=%s | campaign_ref=%s",
                        _safe_hash(wa_message_id),
                        _safe_tail((recent_marketing_row or {}).get("campaign_id")),
                    )
                    await send_whatsapp_message(
                        to_number=from_number,
                        text="No pude completar la baja automática. Escríbenos para ayudarte.",
                        channel=channel,
                    )
                continue

            if recent_marketing_row and _is_marketing_interest_action(
                message_type=message_type,
                user_text=user_text,
                known_opt_out_labels=known_opt_out_labels,
            ):
                handoff_info: dict[str, Any] = {}
                try:
                    # Local import keeps webhook load fast and avoids startup coupling.
                    from api.modules.assistant_rag import intent_router as _intent_router

                    handoff_info = _intent_router._upsert_whatsapp_handoff(
                        client_id=client_id,
                        session_id=session_id,
                        user_message=user_text,
                        ai_message="",
                        trigger="campaign_interest_button",
                        reason="campaign_interest",
                        language=_resolve_interest_language(user_text),
                        metadata_origin="marketing_campaign",
                        metadata_extra={
                            "campaign_id": (recent_marketing_row or {}).get("campaign_id"),
                            "recipient_key": (recent_marketing_row or {}).get("recipient_key"),
                        },
                        alert_type="human_intervention",
                        alert_priority="high",
                        alert_title="Prospect interested in campaign",
                    )
                    logger.info(
                        "Meta campaign-interest handoff result | message_fp=%s | campaign_ref=%s | handoff_ref=%s | reused=%s | alert_created=%s | feature_enabled=%s",
                        _safe_hash(wa_message_id),
                        _safe_tail((recent_marketing_row or {}).get("campaign_id")),
                        _safe_tail((handoff_info or {}).get("handoff_id")),
                        bool((handoff_info or {}).get("reused")),
                        bool((handoff_info or {}).get("alert_created")),
                        bool((handoff_info or {}).get("feature_enabled")),
                    )
                except Exception as handoff_error:
                    logger.exception(
                        "❌ Failed creating campaign-interest handoff | client_ref=%s | session_fp=%s | err=%s",
                        _safe_tail(client_id),
                        _safe_hash(session_id),
                        handoff_error,
                    )

                _log_marketing_interest_event(
                    client_id=client_id,
                    campaign_id=(recent_marketing_row or {}).get("campaign_id"),
                    recipient_key=(recent_marketing_row or {}).get("recipient_key"),
                    provider_message_id=context_message_id or (recent_marketing_row or {}).get("provider_message_id"),
                    handoff_id=(handoff_info or {}).get("handoff_id"),
                )
                upsert_marketing_contact_state(
                    supabase_client=supabase,
                    client_id=client_id,
                    email=(recent_marketing_row or {}).get("email"),
                    phone=(recent_marketing_row or {}).get("phone") or from_number,
                    interest_status="interested",
                )

                if (handoff_info or {}).get("handoff_id"):
                    interest_ack = (
                        "Thanks for your interest. A human advisor will continue with you here."
                        if _resolve_interest_language(user_text) == "en"
                        else "Gracias por tu interés. Un asesor humano continuará contigo por este mismo chat."
                    )
                else:
                    interest_ack = (
                        "Thanks, we got your message. Our team will follow up shortly."
                        if _resolve_interest_language(user_text) == "en"
                        else "Gracias, recibimos tu mensaje. Nuestro equipo te dará seguimiento en breve."
                    )

                await send_whatsapp_message(
                    to_number=from_number,
                    text=interest_ack,
                    channel=channel,
                )
                continue

            # ---------------------------------------------------------
            # Cancelación directa desde botón rápido
            # ---------------------------------------------------------
            if _is_cancel_action(message_type, message, user_text):
                try:
                    cancelled, cancel_msg = await _cancel_appointment_from_whatsapp(
                        client_id=client_id,
                        from_number=from_number,
                    )
                    logger.info(
                        "🧾 WhatsApp cancel action | client_ref=%s | from_fp=%s | cancelled=%s",
                        _safe_tail(client_id),
                        _safe_hash(from_number),
                        cancelled,
                    )
                except Exception:
                    logger.exception(
                        "❌ WhatsApp cancel action failed | client_ref=%s | from_fp=%s",
                        _safe_tail(client_id),
                        _safe_hash(from_number),
                    )
                    cancel_msg = "⚠️ No pude cancelar tu cita en este momento. Intenta de nuevo."

                if cancel_msg:
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
            if assistant_response:
                await send_whatsapp_message(
                    to_number=from_number,
                    text=assistant_response,
                    channel=channel,
                )
            else:
                logger.info(
                    "WhatsApp auto-reply suppressed | message_fp=%s | from_fp=%s",
                    _safe_hash(wa_message_id),
                    _safe_hash(from_number),
                )

            logger.info("WhatsApp message processed | message_fp=%s", _safe_hash(wa_message_id))

    except Exception as e:
        # ⚠️ Nunca levantar excepción aquí
        # Meta YA recibió 200 OK
        logger.exception("❌ WhatsApp background error: %s", str(e))
