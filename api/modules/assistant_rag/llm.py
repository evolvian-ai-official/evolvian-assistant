import os
import logging
from openai import OpenAI

logger = logging.getLogger("llm")

# Inicializa cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def openai_chat(messages, temperature: float = 0.7, model: str = None) -> str:
    """
    Envía mensajes al modelo de chat de OpenAI.
    Compatible con el modo directo usado en calendar_prompt, email, etc.
    """
    try:
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        content = response.choices[0].message.content.strip()
        logger.info(f"💬 OpenAI response (truncated): {content[:150]}...")
        return content

    except Exception as e:
        logger.error(f"❌ Error in openai_chat: {e}")
        return "Error: the AI assistant could not process your request."
