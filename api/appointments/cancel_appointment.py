from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from html import escape
import uuid
import logging

from api.config.config import supabase
from api.authz import authorize_client_request
from api.appointments.cancellation_notifications import (
    send_appointment_cancellation_notification,
    send_appointment_cancellation_email_notification,
)
from api.appointments.cancel_link_tokens import verify_cancel_token

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================
# Payload
# =========================
class CancelAppointmentPayload(BaseModel):
    client_id: uuid.UUID
    appointment_id: uuid.UUID
    reason: Optional[str] = "user_cancelled"


def _html_page(
    message: str,
    title: str = "Cancelación de cita",
    action_html: str = "",
) -> HTMLResponse:
    safe_title = escape(title)
    safe_message = escape(message)
    html = f"""
    <!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="noindex,nofollow" />
        <title>{safe_title}</title>
        <style>
          body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: #f6f8fb;
            color: #1f2937;
            margin: 0;
            padding: 24px;
          }}
          .card {{
            max-width: 560px;
            margin: 64px auto;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
          }}
          h1 {{ margin: 0 0 12px; font-size: 1.25rem; }}
          p {{ margin: 0; line-height: 1.45; }}
          .actions {{ margin-top: 16px; }}
          .btn {{
            display: inline-block;
            padding: 10px 14px;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            background: #f8fafc;
            color: #334155;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
          }}
          .btn:focus {{ outline: 2px solid #94a3b8; outline-offset: 2px; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>{safe_title}</h1>
          <p>{safe_message}</p>
          {action_html}
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


def _resolve_cancel_context(token: str) -> tuple[Optional[dict], Optional[HTMLResponse]]:
    token_value = str(token or "").strip()
    payload = verify_cancel_token(token_value)
    if not payload:
        return None, _html_page("El enlace de cancelación es inválido o ya expiró.", "Enlace inválido")

    client_id = str(payload.get("cid") or "").strip()
    appointment_id = str(payload.get("aid") or "").strip()
    token_email = str(payload.get("em") or "").strip().lower()
    if not client_id or not appointment_id:
        return None, _html_page("No se pudo validar el enlace de cancelación.", "Enlace inválido")

    res = (
        supabase
        .table("appointments")
        .select("id, status, user_name, user_email, user_phone, scheduled_time, appointment_type")
        .eq("id", appointment_id)
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    appointment = res.data
    if not appointment:
        return None, _html_page("No encontramos la cita asociada a este enlace.", "Cita no encontrada")

    db_email = str(appointment.get("user_email") or "").strip().lower()
    if token_email and db_email and token_email != db_email:
        return None, _html_page("Este enlace no corresponde al correo de la cita.", "Enlace inválido")

    return {
        "client_id": client_id,
        "appointment_id": appointment_id,
        "appointment": appointment,
    }, None


async def _cancel_appointment_record(
    *,
    appointment: dict,
    client_id: str,
    appointment_id: str,
    usage_channel: str,
    usage_action: str,
) -> tuple[bool, int]:
    if appointment.get("status") == "cancelled":
        return True, 0

    now_iso = datetime.utcnow().isoformat()

    supabase.table("appointments").update({
        "status": "cancelled",
        "updated_at": now_iso,
    }).eq("id", appointment_id).eq("client_id", client_id).execute()

    reminders_res = (
        supabase
        .table("appointment_reminders")
        .update({
            "status": "cancelled",
            "updated_at": now_iso,
        })
        .eq("appointment_id", appointment_id)
        .eq("client_id", client_id)
        .in_("status", ["pending", "processing", "sending"])
        .execute()
    )
    cancelled_reminders = len(reminders_res.data or [])

    try:
        await send_appointment_cancellation_notification({
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
            "❌ Appointment cancellation WhatsApp notification crashed | client_id=%s | appointment_id=%s",
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
            "❌ Appointment cancellation email notification crashed | client_id=%s | appointment_id=%s",
            client_id,
            appointment_id,
        )

    supabase.table("appointment_usage").insert({
        "client_id": client_id,
        "appointment_id": appointment_id,
        "channel": usage_channel,
        "action": usage_action,
        "created_at": now_iso,
    }).execute()

    return False, cancelled_reminders


# =========================
# Endpoint
# =========================
@router.post("/appointments/cancel", tags=["Appointments"])
async def cancel_appointment(payload: CancelAppointmentPayload, request: Request):
    """
    Soft-cancels an appointment:
    - Updates appointment.status = 'cancelled'
    - Cancels all pending reminders
    - Tracks usage

    ⚠️ No deletes. Fully auditable.
    """

    client_id = str(payload.client_id)
    appointment_id = str(payload.appointment_id)
    authorize_client_request(request, client_id)

    # =========================
    # 1️⃣ Load appointment (ownership + status)
    # =========================
    res = (
        supabase
        .table("appointments")
        .select("id, status, user_name, user_email, user_phone, scheduled_time")
        .eq("id", appointment_id)
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )

    appointment = res.data

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found for this client"
        )

    already_cancelled, cancelled_reminders = await _cancel_appointment_record(
        appointment=appointment,
        client_id=client_id,
        appointment_id=appointment_id,
        usage_channel="system",
        usage_action="cancelled",
    )

    if already_cancelled:
        logger.info(f"ℹ️ Appointment already cancelled: {appointment_id}")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "status": "cancelled",
            "already_cancelled": True
        }

    logger.info(f"❌ Appointment cancelled: {appointment_id}")
    logger.info(f"⏰ Reminders cancelled: {cancelled_reminders}")

    # =========================
    # 3️⃣ Response
    # =========================
    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": "cancelled",
        "reminders_cancelled": cancelled_reminders,
        "reason": payload.reason,
    }


@router.get("/appointments/cancel/by-link", response_class=HTMLResponse, include_in_schema=False)
async def cancel_appointment_by_link(token: Optional[str] = Query(default=None)):
    context, error_response = _resolve_cancel_context(token or "")
    if error_response:
        return error_response

    appointment = context["appointment"]
    if appointment.get("status") == "cancelled":
        return _html_page("La cita ya estaba cancelada. No necesitas hacer nada más.", "Cita ya cancelada")

    safe_token = escape(str(token or ""), quote=True)
    action_html = f"""
    <div class="actions">
      <form method="post" action="/appointments/cancel/by-link">
        <input type="hidden" name="token" value="{safe_token}" />
        <button type="submit" class="btn">Confirmar cancelación</button>
      </form>
    </div>
    """
    return _html_page(
        "Estás por cancelar tu cita. Esta acción no se puede deshacer.",
        "Confirmar cancelación",
        action_html=action_html,
    )


@router.post("/appointments/cancel/by-link", response_class=HTMLResponse, include_in_schema=False)
async def cancel_appointment_by_link_submit(
    request: Request,
    token: Optional[str] = Query(default=None),
):
    token_value = str(token or "").strip()
    if not token_value:
        try:
            form_data = await request.form()
            token_value = str(form_data.get("token") or "").strip()
        except Exception:
            token_value = ""

    context, error_response = _resolve_cancel_context(token_value)
    if error_response:
        return error_response

    appointment = context["appointment"]
    client_id = context["client_id"]
    appointment_id = context["appointment_id"]

    already_cancelled, _ = await _cancel_appointment_record(
        appointment=appointment,
        client_id=client_id,
        appointment_id=appointment_id,
        usage_channel="email",
        usage_action="cancelled_from_email_link",
    )
    if already_cancelled:
        return _html_page("La cita ya estaba cancelada. No necesitas hacer nada más.", "Cita ya cancelada")

    return _html_page(
        "Tu cita fue cancelada correctamente. Si deseas reprogramarla, responde a nuestros canales de contacto.",
        "Cita cancelada",
    )
