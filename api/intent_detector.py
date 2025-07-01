# api/modules/assistant_rag/intent_detector.py

def detect_intent_to_schedule(message: str) -> bool:
    """
    Detecta si el usuario tiene intención de agendar una cita.
    Devuelve True si encuentra frases relacionadas a agendar/reservar.
    """
    message = message.lower()

    keywords = [
        "quiero agendar",
        "reservar cita",
        "quiero una cita",
        "puedo agendar",
        "agenda",
        "agéndame",
        "confirmar cita",
        "me gustaría agendar",
        "agendar a las",
        "agendar para el",
        "agendar para el día",
        "hacer una cita",
        "necesito una cita",
        "quiero reservar",
        "programar una cita",
        "quiero programar",
        "puedes agendar",
        "hazme una cita",
        "necesito agendar"
    ]

    return any(kw in message for kw in keywords)
