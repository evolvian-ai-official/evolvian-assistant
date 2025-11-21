import os
import logging
from openai import OpenAI

logger = logging.getLogger("llm")

# Inicializa cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Premium calendar models
CALENDAR_MODEL_PREMIUM = "gpt-4.1"
CALENDAR_MODEL_FALLBACK = "gpt-4.1-mini"

# Global fallback (no calendar)
GLOBAL_FALLBACK_MODEL = "gpt-4o-mini"


def openai_chat(
    messages,
    temperature: float = 0.1,
    model: str = None,
    use_calendar_model: bool = False,
    timeout: int = 12
) -> str:
    """
    ============================================================
    Evolvian AI — OpenAI Chat Wrapper (Production Grade)
    ------------------------------------------------------------
    - If use_calendar_model=True → force premium gpt-4.1
    - Otherwise → use provided model or OPENAI_MODEL
    - Includes:
        ✔ Timeout
        ✔ Premium fallback
        ✔ Global fallback
        ✔ Logging
        ✔ Error insulation for Render & Supabase pipelines
    ============================================================
    """

    # 1️⃣ Modelo seleccionado según el flujo
    if use_calendar_model:
        selected_model = CALENDAR_MODEL_PREMIUM
    else:
        selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # 2️⃣ Intento principal
    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
        content = response.choices[0].message.content.strip()
        logger.info(f"💬 OpenAI response ({selected_model}) → {content[:180]}...")
        return content

    except Exception as e:
        logger.error(f"❌ Error using {selected_model}: {e}")


    # 3️⃣ Fallback exclusivo para calendario (premium → mini)
    if use_calendar_model and selected_model != CALENDAR_MODEL_FALLBACK:
        try:
            logger.warning(f"⚠️ Switching to fallback PREMIUM: {CALENDAR_MODEL_FALLBACK}")

            response = client.chat.completions.create(
                model=CALENDAR_MODEL_FALLBACK,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            content = response.choices[0].message.content.strip()
            return content

        except Exception as e2:
            logger.error(f"❌ Calendar fallback (gpt-4.1-mini) also failed: {e2}")


    # 4️⃣ Fallback global (para cualquier flujo NO calendar)
    if not use_calendar_model:
        try:
            logger.warning(f"⚠️ Switching to GLOBAL FALLBACK: {GLOBAL_FALLBACK_MODEL}")

            response = client.chat.completions.create(
                model=GLOBAL_FALLBACK_MODEL,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            content = response.choices[0].message.content.strip()
            return content

        except Exception as e3:
            logger.error(f"❌ Global fallback failed: {e3}")


    # 5️⃣ Último recurso si todo falla
    return "Error: the AI assistant could not process your request."
