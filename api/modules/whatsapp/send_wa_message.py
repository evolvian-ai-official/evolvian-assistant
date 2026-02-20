import requests
from typing import List, Optional

from api.modules.assistant_rag.supabase_client import supabase
from api.security.whatsapp_token_crypto import decrypt_whatsapp_token


# =====================================================
# 1️⃣ FUNCIÓN LEGACY — NO SE TOCA
# =====================================================
def send_whatsapp_message(
    to_number: str,
    message: str,
    token: str,
    phone_id: str,
    image_url: Optional[str] = None,
    buttons: Optional[List[str]] = None
) -> bool:
    """
    Envía un mensaje directo a WhatsApp usando credenciales explícitas.
    ⚠️ Esta función NO debe romperse (chat, widget, flows actuales).
    """

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
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"btn_{i+1}",
                                "title": btn
                            }
                        }
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
        print(f"📤 Enviando WhatsApp a {to_number}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        print(f"✅ WhatsApp enviado correctamente | Status: {response.status_code}")
        return True

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ Error HTTP WhatsApp: {http_err}")
        print(f"📩 Respuesta Meta: {response.text}")

    except Exception as e:
        print(f"❌ Error inesperado WhatsApp: {e}")

    return False


# =====================================================
# 2️⃣ WRAPPER NUEVO — PARA REMINDERS / OUTBOUND
# =====================================================
def send_whatsapp_message_for_client(
    client_id: str,
    to_number: str,
    message: str,
    image_url: Optional[str] = None,
    buttons: Optional[List[str]] = None
) -> bool:
    """
    Envía un mensaje WhatsApp resolviendo automáticamente
    las credenciales del cliente desde la DB.
    👉 Usar SOLO para reminders, campañas, outbound, cron jobs.
    """

    # 🔎 Buscar configuración WhatsApp activa del cliente
    resp = (
        supabase
        .table("channels")
        .select("wa_phone_id, wa_token")
        .eq("client_id", client_id)
        .eq("type", "whatsapp")
        .eq("is_active", True)
        .single()
        .execute()
    )

    if not resp.data:
        print(f"❌ WhatsApp no configurado para client_id={client_id}")
        return False

    wa_phone_id = resp.data.get("wa_phone_id")
    wa_token = decrypt_whatsapp_token(resp.data.get("wa_token"))

    if not wa_phone_id or not wa_token:
        print(
            f"❌ Credenciales WhatsApp incompletas "
            f"(phone_id={wa_phone_id}, token={'OK' if wa_token else 'MISSING'})"
        )
        return False

    # 🚀 Delegar envío al sender legacy
    return send_whatsapp_message(
        to_number=to_number,
        message=message,
        token=wa_token,
        phone_id=wa_phone_id,
        image_url=image_url,
        buttons=buttons
    )
