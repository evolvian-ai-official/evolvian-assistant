import os
import requests
import logging
from typing import Optional

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
logger = logging.getLogger(__name__)


def send_confirmation_email(
    to_email: str,
    date_str: str,
    hour_str: str,
    html_body: Optional[str] = None,
    subject: Optional[str] = None,
):
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
            "from": "Evolvian AI <noreply@notifications.evolvianai.com>",
            "to": [to_email],
            "subject": subject or "✅ Confirmación de tu cita",
            "html": html_body or f"""
                <p>Hola 👋</p>
                <p>Tu cita ha sido agendada para el <strong>{date_str}</strong> a las <strong>{hour_str}</strong>.</p>
                <p>Gracias por usar Evolvian AI 💙</p>
                <p style='color:#888;font-size:12px;'>Enviado automáticamente por Evolvian AI</p>
            """,
        },
    )

    if response.status_code != 200:
        logger.error(f"❌ Error al enviar correo: {response.status_code} - {response.text}")
    else:
        logger.info(f"✅ Correo de confirmación enviado correctamente a {to_email}")
