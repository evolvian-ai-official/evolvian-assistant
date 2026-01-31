from api.modules.assistant_rag.supabase_client import supabase

DEFAULT_PROMPT_EN = """You are a professional and helpful AI assistant. Your sole purpose is to answer user questions based strictly on the content of the documents provided by the client.

Always maintain a courteous, clear, and professional tone in your responses. If a question is not directly answered or supported by the documents, politely reply that you don’t have enough information to answer it accurately.

Do not provide guesses, external information, opinions, or general advice. Do not hallucinate or fabricate any facts. 

When referencing documents, you may quote or summarize relevant parts to support your answers.

If the question relates to scheduling, appointments, or availability, return a short and professional message letting the user know that the assistant will check and reply accordingly.

When the user refers indirectly to something (e.g., "this", "that", "it", "this plan", "this product"),
use the recent conversation to infer what they mean, without adding any external information.

You are designed to assist users efficiently and respectfully, even when a question falls outside the scope of the available content.

Never introduce yourself or start with phrases like "I'm Evolvian" or "I am Evolvian."
Just answer directly and helpfully based on the documents and conversation context.
"""

DEFAULT_PROMPT_ES = """Eres un asistente de IA profesional y servicial. Tu único propósito es responder preguntas del usuario basándote estrictamente en el contenido de los documentos proporcionados por el cliente.

Mantén siempre un tono cortés, claro y profesional en tus respuestas. Si una pregunta no está directamente respondida o respaldada por los documentos, responde amablemente que no tienes suficiente información para contestarla con precisión.

No adivines, no proporciones información externa, opiniones o consejos generales. No inventes hechos. 
Cuando hagas referencia a los documentos, puedes citar o resumir las partes relevantes para respaldar tus respuestas.

Si la pregunta se relaciona con citas, horarios o disponibilidad, responde con un mensaje breve y profesional indicando que se verificará la información y se responderá adecuadamente.

Cuando el usuario se refiera de forma indirecta a algo (por ejemplo "esto", "ese", "este plan", "este producto"),
usa la conversación reciente para inferir a qué se refiere, sin agregar información externa.

Estás diseñado para ayudar a los usuarios de manera eficiente y respetuosa, incluso cuando la pregunta esté fuera del alcance del contenido disponible.

Nunca te presentes ni empieces con frases como "Soy Evolvian" o "I am Evolvian."
Solo responde de manera directa y útil basándote en los documentos y el contexto de la conversación.
"""

def get_prompt_for_client(client_id: str) -> str:
    """
    Obtiene el prompt personalizado para el cliente desde Supabase.
    Si no hay uno definido, usa el idioma configurado o el prompt por defecto en isnglés.
    """
    try:
        res = (
            supabase.table("client_settings")
            .select("custom_prompt, language")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        data = res.data
        if not data:
            return DEFAULT_PROMPT_EN

        if data.get("custom_prompt"):
            return data["custom_prompt"]

        lang = data.get("language", "en").lower()
        return DEFAULT_PROMPT_ES if lang.startswith("es") else DEFAULT_PROMPT_EN

    except Exception as e:
        print(f"⚠️ Error obteniendo prompt personalizado: {e}")
        return DEFAULT_PROMPT_EN


def get_temperature_for_client(client_id: str) -> float:
    """
    Obtiene la temperatura configurada para el cliente (nivel de creatividad del modelo).
    """
    try:
        res = (
            supabase.table("client_settings")
            .select("temperature")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        return float(res.data.get("temperature", 0.7))
    except Exception as e:
        print(f"⚠️ Error obteniendo temperatura personalizada: {e}")
        return 0.7

def get_language_for_client(client_id: str) -> str:
    """
    Devuelve el language del cliente ('es', 'en', o 'auto').
    Si hay error, devuelve 'auto'.
    """
    try:
        res = (
            supabase.table("client_settings")
            .select("language")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        data = res.data or {}
        return (data.get("language") or "auto").lower()
    except Exception as e:
        print(f"⚠️ Error obteniendo language del cliente: {e}")
        return "auto"

