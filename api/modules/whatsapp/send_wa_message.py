import requests

def send_whatsapp_message(to_number: str, message: str, token: str, phone_id: str) -> bool:
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ Mensaje enviado a {to_number}")
        return True
    except Exception as e:
        print(f"❌ Error enviando mensaje a WhatsApp: {e}")
        return False
