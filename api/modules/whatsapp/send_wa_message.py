import requests
from typing import List, Optional

def send_whatsapp_message(
    to_number: str,
    message: str,
    token: str,
    phone_id: str,
    image_url: Optional[str] = None,
    buttons: Optional[List[str]] = None
) -> bool:
    # ✅ Asegurar formato internacional E.164
    if not to_number.startswith("+"):
        to_number = f"+{to_number}"
        print(f"📞 Número corregido a formato internacional: {to_number}")

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # ✅ Mensaje con botones
    if buttons and 1 <= len(buttons) <= 3:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"btn_{i+1}", "title": btn}}
                        for i, btn in enumerate(buttons)
                    ]
                }
            }
        }

    # ✅ Mensaje con imagen
    elif image_url:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": message
            }
        }

    # ✅ Mensaje de texto simple
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {
                "body": message
            }
        }

    try:
        print(f"📤 Enviando mensaje a {to_number} con payload: {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ Mensaje enviado correctamente. Status: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ Error HTTP al enviar mensaje: {http_err} | Código: {response.status_code}")
        print(f"📩 Respuesta de Meta: {response.text}")
    except Exception as e:
        print(f"❌ Error inesperado enviando mensaje a WhatsApp: {e}")
    return False
