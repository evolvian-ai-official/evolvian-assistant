from twilio.rest import Client

# Reemplaza con tus credenciales reales de Twilio
account_sid = "AC9905a1a3fac0543e8a92898d9403d75b"
auth_token = "abf86e4daa108a2f4d6fd398859252b7"
twilio_number = "+19388677278"  # Reemplaza por tu número Twilio

client = Client(account_sid, auth_token)

# Obtener últimos 5 mensajes recibidos
messages = client.messages.list(to=twilio_number, limit=5)

for msg in messages:
    print(f"De: {msg.from_}")
    print(f"Mensaje: {msg.body}")
    print("------")
