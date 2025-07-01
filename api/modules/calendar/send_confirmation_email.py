# api/modules/calendar/send_confirmation_email.py

import os
import requests
import logging

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_confirmation_email(to_email: str, date_str: str, hour_str: str):
    if not RESEND_API_KEY:
        logging.error("❌ RESEND_API_KEY no está definido.")
        return

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": "Evolvian <noreply@evolvian.ai>",
            "to": [to_email],
            "subject": "✅ Confirmación de tu cita",
            "html": f"<p>Tu cita ha sido agendada para el <strong>{date_str}</strong> a las <strong>{hour_str}</strong>.</p><p>Gracias por usar Evolvian!</p>",
        },
    )

    if response.status_code != 200:
        logging.error(f"❌ Error al enviar correo: {response.status_code} - {response.text}")
    else:
        logging.info("✅ Correo de confirmación enviado correctamente.")
