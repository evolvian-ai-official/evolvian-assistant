import os
import requests

def notify_business_owner(empresa_email: str, slot_time: str, user_email: str, user_name: str):
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY no definido")

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "from": "Evolvian AI <notificaciones@evolvian.ai>",
        "to": [empresa_email],
        "subject": "📅 Nueva cita agendada",
        "html": f"""
        <p>Hola,</p>
        <p>Se ha agendado una nueva cita a través de tu asistente Evolvian:</p>
        <ul>
          <li><strong>Fecha y hora:</strong> {slot_time}</li>
          <li><strong>Nombre del usuario:</strong> {user_name}</li>
          <li><strong>Email del usuario:</strong> {user_email}</li>
        </ul>
        <p>Consulta tu calendario o tu panel para más información.</p>
        """
    }

    response = requests.post("https://api.resend.com/emails", headers=headers, json=body)
    if response.status_code >= 400:
        raise Exception(f"❌ Error al enviar correo: {response.status_code} - {response.text}")
