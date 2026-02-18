import os
import base64
import requests
import logging
from typing import Optional
from datetime import datetime
from email.mime.text import MIMEText

from api.config.config import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
logger = logging.getLogger(__name__)


def _get_client_sender_name(client_id: Optional[str]) -> str:
    default_name = "Tu empresa"
    if not client_id:
        return default_name

    try:
        profile_res = (
            supabase
            .table("client_profile")
            .select("company_name")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        if profile_res.data:
            company_name = (profile_res.data[0].get("company_name") or "").strip()
            if company_name:
                return company_name
    except Exception as e:
        logger.warning("⚠️ Could not load client_profile.company_name | client_id=%s | error=%s", client_id, e)

    try:
        client_res = (
            supabase
            .table("clients")
            .select("name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        if client_res.data:
            client_name = (client_res.data[0].get("name") or "").strip()
            if client_name:
                return client_name
    except Exception as e:
        logger.warning("⚠️ Could not load clients.name | client_id=%s | error=%s", client_id, e)

    return default_name


def _safe_header_name(value: str) -> str:
    return (value or "").replace("\r", " ").replace("\n", " ").strip() or "Tu empresa"


def _render_template_text(template_text: Optional[str], replacements: dict[str, str]) -> Optional[str]:
    if not template_text:
        return template_text
    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value or "")
    return rendered


def _resolve_template_content(
    *,
    client_id: Optional[str],
    default_subject: str,
    default_html: str,
    date_str: str,
    hour_str: str,
    user_name: Optional[str],
    appointment_type: Optional[str],
) -> tuple[str, str, Optional[str]]:
    final_subject = default_subject
    final_html = default_html

    if not client_id:
        return final_subject, final_html, None

    try:
        tpl_res = (
            supabase
            .table("message_templates")
            .select("id, body, label")
            .eq("client_id", client_id)
            .eq("type", "appointment_confirmation")
            .eq("channel", "email")
            .eq("is_active", True)
            .limit(20)
            .execute()
        )
        templates = tpl_res.data or []
        if not templates:
            return final_subject, final_html, None

        tpl = next(
            (
                row for row in templates
                if isinstance(row.get("body"), str) and row.get("body", "").strip()
            ),
            None,
        )
        if not tpl:
            logger.warning(
                "⚠️ appointment_confirmation template(s) found but none has body | client_id=%s | count=%s",
                client_id,
                len(templates),
            )
            return final_subject, final_html, None

        company_name = _get_client_sender_name(client_id)
        now_label = datetime.utcnow().strftime("%Y-%m-%d")
        scheduled_label = f"{date_str} {hour_str}".strip()

        replacements = {
            "company_name": company_name,
            "user_name": (user_name or "Cliente").strip() or "Cliente",
            "appointment_type": (appointment_type or "").strip(),
            "scheduled_time": scheduled_label,
            "appointment_date": date_str,
            "appointment_time": hour_str,
            "current_date": now_label,
        }

        rendered_html = _render_template_text(tpl.get("body", ""), replacements)
        rendered_subject = _render_template_text((tpl.get("label") or "").strip(), replacements)

        if rendered_html:
            final_html = rendered_html
        if rendered_subject:
            final_subject = rendered_subject.replace("\r", " ").replace("\n", " ").strip() or final_subject
        return final_subject, final_html, str(tpl.get("id")) if tpl.get("id") else None

    except Exception as e:
        logger.warning("⚠️ Could not resolve confirmation template | client_id=%s | error=%s", client_id, e)

    return final_subject, final_html, None


def _send_via_client_gmail(
    *,
    client_id: str,
    to_email: str,
    subject: str,
    html_body: str,
    content_source: str,
    template_id: Optional[str],
) -> bool:
    try:
        try:
            channel_res = (
                supabase
                .table("channels")
                .select("*")
                .eq("client_id", client_id)
                .eq("type", "email")
                .eq("provider", "gmail")
                .eq("active", True)
                .limit(1)
                .execute()
            )
        except Exception as e:
            err_text = str(e).lower()
            if "column channels.active does not exist" not in err_text and "channels.active" not in err_text:
                raise
            channel_res = (
                supabase
                .table("channels")
                .select("*")
                .eq("client_id", client_id)
                .eq("type", "email")
                .eq("provider", "gmail")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
        channel = (channel_res.data or [None])[0]
        if not channel or not channel.get("gmail_access_token"):
            return False

        service = get_gmail_service(channel)

        msg = MIMEText(html_body, "html")
        msg["to"] = to_email
        msg["subject"] = subject
        sender_name = _safe_header_name(_get_client_sender_name(client_id))
        sender_email = (channel.get("value") or "").strip()
        msg["from"] = f"{sender_name} <{sender_email}>" if sender_email else sender_name

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

        logger.info(
            "✅ Confirmation email sent via client Gmail | client_id=%s | from=%s | source=%s | template_id=%s",
            client_id,
            channel.get("value"),
            content_source,
            template_id or "-",
        )
        return True
    except Exception as e:
        logger.warning("⚠️ Gmail send fallback to Resend | client_id=%s | error=%s", client_id, e)
        return False


def send_confirmation_email(
    to_email: str,
    date_str: str,
    hour_str: str,
    html_body: Optional[str] = None,
    subject: Optional[str] = None,
    client_id: Optional[str] = None,
    user_name: Optional[str] = None,
    appointment_type: Optional[str] = None,
):
    default_subject = subject or "✅ Confirmación de tu cita"
    sender_name = _safe_header_name(_get_client_sender_name(client_id))
    default_html = html_body or f"""
                <p>Hola 👋</p>
                <p>Tu cita ha sido agendada para el <strong>{date_str}</strong> a las <strong>{hour_str}</strong>.</p>
                <p>Gracias por tu tiempo.</p>
                <p style='color:#888;font-size:12px;'>Enviado automáticamente por {sender_name}</p>
            """
    if html_body is not None and subject is not None:
        content_source = "provided_template"
    elif html_body is not None or subject is not None:
        content_source = "provided_partial"
    else:
        content_source = "default_fallback"

    template_id = None
    final_subject, final_html = default_subject, default_html
    if client_id and (html_body is None or subject is None):
        resolved_subject, resolved_html, resolved_template_id = _resolve_template_content(
            client_id=client_id,
            default_subject=default_subject,
            default_html=default_html,
            date_str=date_str,
            hour_str=hour_str,
            user_name=user_name,
            appointment_type=appointment_type,
        )
        final_subject, final_html = resolved_subject, resolved_html
        if resolved_template_id:
            content_source = "db_template"
            template_id = resolved_template_id

    logger.info(
        "📧 Confirmation email content selected | client_id=%s | to=%s | source=%s | template_id=%s",
        client_id or "-",
        to_email,
        content_source,
        template_id or "-",
    )

    if client_id:
        sent_by_gmail = _send_via_client_gmail(
            client_id=client_id,
            to_email=to_email,
            subject=final_subject,
            html_body=final_html,
            content_source=content_source,
            template_id=template_id,
        )
        if sent_by_gmail:
            return

    if not RESEND_API_KEY:
        logger.error("❌ RESEND_API_KEY no está definido.")
        return

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": f"{sender_name} <noreply@notifications.evolvianai.com>",
            "to": [to_email],
            "subject": final_subject,
            "html": final_html,
        },
    )

    if response.status_code != 200:
        logger.error(f"❌ Error al enviar correo: {response.status_code} - {response.text}")
    else:
        logger.info(
            "✅ Correo de confirmación enviado por Resend | to=%s | source=%s | template_id=%s",
            to_email,
            content_source,
            template_id or "-",
        )
