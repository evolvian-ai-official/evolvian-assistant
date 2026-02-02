"""
BASE5 - Evolvian RAG Final (seguro, flexible y anti-hallucination)
✅ FIX: idioma consistente + system role real + no contaminar question original
"""

import os
import logging

from typing import List, Dict, Optional, Union
import uuid
from api.config.config import DEFAULT_CHAT_MODEL

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma

from langchain_core.messages import SystemMessage, HumanMessage

from api.modules.assistant_rag.supabase_client import (
    save_history,
   
)
from api.modules.assistant_rag.prompt_utils import (
    get_prompt_for_client,
    get_temperature_for_client,
    get_language_for_client,  # ✅ NUEVO (abajo te dejo el cambio)
)

# 🚫 Desactivar telemetría de Chroma
os.environ["ANONYMIZED_TELEMETRY"] = "false"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


FALLBACK_BY_LANG = {
    "es": "No tengo información para responder esta pregunta.Si tienes una duda relacionada con este negocio y necesitas más detalle, puedes contactarnos directamente. Mientras tanto, con gusto puedo ayudarte con cualquier otra pregunta.",
    "en": "I don’t have information to answer this question. If you have a question related to this business and need more details, you can contact us directly. In the meantime, I’m happy to help with any other question.",
}


def get_base_data_path() -> str:
    render_root = "/opt/render/project/src"
    base_dir = os.path.join(render_root, "data") if os.path.exists(render_root) else os.path.join(os.getcwd(), "data")
    os.makedirs(base_dir, exist_ok=True)
    logging.info(f"📂 Base data path usada: {base_dir}")
    return base_dir





def _guess_lang_es_en(text: str) -> str:
    """
    Heurística rápida y robusta para detectar ES / EN en mensajes cortos.
    Optimizada para chat real (sin acentos, sin signos).
    """
    t = (text or "").strip().lower()
    if not t:
        return "en"

    # 1️⃣ Señales fuertes de español
    if any(c in t for c in "¿¡ñáéíóú"):
        return "es"

    # 2️⃣ Palabras funcionales MUY comunes en español (chat real)
    es_words = {
        "que", "es", "como", "para", "por", "porque", "cuando", "donde",
        "cual", "cuanto", "cuantos",
        "hola", "buenas", "dame", "quiero", "necesito",
        "informacion", "información", "info",
        "plan", "planes", "precio", "coste", "costo",
        "ayuda", "soporte", "incluye", "incluyen",
        "funciona", "servicio"
    }

    # limpieza básica
    tokens = set(
        t.replace("?", "")
         .replace("¿", "")
         .replace("!", "")
         .replace("¡", "")
         .split()
    )

    if tokens.intersection(es_words):
        return "es"

    # 3️⃣ Default conservador
    return "en"


def _filter_conversation_by_lang(conversation: str, lang: str) -> str:
    """
    Filtra el historial para conservar solo las líneas
    que coinciden con el idioma del turno actual.
    """
    if not conversation:
        return ""

    lines = conversation.split("\n")
    filtered = []

    for line in lines:
        if _guess_lang_es_en(line) == lang:
            filtered.append(line)

    return "\n".join(filtered)



def _safe_langdetect(text: str) -> Optional[str]:
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return None


def _resolve_user_language(client_id: str, user_text: str) -> str:
    """
    Decide el idioma del turno según el MENSAJE del usuario.
    El idioma del cliente actúa solo como fallback.

    Prioridad:
    1) Heurística ES/EN sobre el mensaje
    2) langdetect (opcional)
    3) client_settings.language
    4) fallback 'en'
    """

    # 1️⃣ Heurística rápida (inputs cortos, chats)
    heuristic = _guess_lang_es_en(user_text)
    if heuristic in ("es", "en"):
        return heuristic

    # 2️⃣ Detección probabilística (backup)
    detected = _safe_langdetect(user_text)
    if detected in ("es", "en"):
        return detected

    # 3️⃣ Idioma configurado del cliente (fallback)
    client_lang = (get_language_for_client(client_id) or "").strip().lower()
    if client_lang.startswith("es"):
        return "es"
    if client_lang.startswith("en"):
        return "en"

    # 4️⃣ Último fallback
    return "en"



def _translate_text(text: str, target_lang: str) -> str:
    """
    Traduce SOLO para retrieval.
    ❌ No afecta idioma de salida final
    ❌ No retraduce si ya está en el idioma correcto
    ✅ Determinista y controlado
    """
    if not text.strip():
        return text

    # Detectar idioma del texto (heurístico, rápido y suficiente)
    detected_lang = _guess_lang_es_en(text)
    if detected_lang == target_lang:
        return text  # 🚫 No retraducir

    if target_lang not in ("es", "en"):
        return text  # 🚫 No traducir a idiomas no soportados

    llm_tr = ChatOpenAI(
        model="gpt-4o-mini",  # modelo estable y barato
        temperature=0
    )

    target_name = "Spanish" if target_lang == "es" else "English"

    resp = llm_tr.invoke([
        SystemMessage(
            content="You are a translation engine. Return ONLY the translated text."
        ),
        HumanMessage(
            content=f"Translate the following text to {target_name}:\n\n{text}"
        )
    ])

    translated = (resp.content or "").strip()
    return translated or text



def _rewrite_for_retrieval(conversation_memory: str, retrieval_question: str) -> str:
    """
    Reescribe la pregunta SOLO para mejorar retrieval.
    ❌ No detecta idioma
    ❌ No traduce
    ❌ No decide lenguaje
    ✅ Usa exactamente el idioma del texto recibido
    """
    if not retrieval_question or not retrieval_question.strip():
        return retrieval_question

    # Si no hay conversación previa, no reescribimos
    if not conversation_memory or not conversation_memory.strip():
        return retrieval_question

    llm_rw = ChatOpenAI(
        model="gpt-4o-mini",  # modelo estable y determinista
        temperature=0
    )

    prompt = f"""
Rewrite the user's question into a clear, standalone question.
Use ONLY the information explicitly present in the conversation.
Do NOT add assumptions or new facts.
If the question is already clear, return it unchanged.

Conversation:
{conversation_memory}

Question:
{retrieval_question}
""".strip()

    resp = llm_rw.invoke([
        SystemMessage(
            content="You rewrite questions for retrieval. Do not add new facts."
        ),
        HumanMessage(content=prompt)
    ])

    rewritten = (resp.content or "").strip()
    return rewritten or retrieval_question



def ask_question(
    messages: Union[List[Dict[str, str]], str],
    client_id: str,
    session_id: str = None,
    disable_rag: bool = False
) -> str:
    try:
        session_id = session_id or str(uuid.uuid4())

        prompt = get_prompt_for_client(client_id)
        temperature = get_temperature_for_client(client_id)
        show_sources = os.getenv("EVOLVIAN_SHOW_SOURCES", "false").lower() == "true"

        # 🔧 Normalizar mensajes
        if isinstance(messages, list):
            norm_messages = [
                {
                    "role": (m.get("role", "user") or "user").strip(),
                    "content": (m.get("content") or "").strip()
                }
                for m in messages if m.get("content")
            ]
        else:
            norm_messages = [{"role": "user", "content": str(messages).strip()}]

        last_user_msg = next(
            (m for m in reversed(norm_messages) if m["role"] == "user"),
            None
        )
        question = (last_user_msg["content"] if last_user_msg else "").strip()
        if not question:
            return ("No logré entender tu mensaje ¿Podrías intentarlo de nuevo?"
            if turn_lang == "es"
            else "I couldn’t understand your message. Could you please try again?"
        )


        # ✅ Guardar original SIEMPRE
        original_question = question

        # 🔒 Idioma del turno (DECISIÓN ÚNICA)
        turn_lang = _resolve_user_language(client_id, original_question)
        fallback = FALLBACK_BY_LANG.get(turn_lang, FALLBACK_BY_LANG["en"])

        logging.info(f"🧩 Pregunta procesada: {original_question}")
        logging.info(f"🈶 Idioma del turno: {turn_lang}")

        # 🧹 Construir y filtrar historial por idioma
        convo_tail = norm_messages[-10:]
        raw_conversation_memory = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in convo_tail
        )
        conversation_memory = _filter_conversation_by_lang(
            raw_conversation_memory,
            turn_lang
        )

        # 👋 Saludo rápido (controlado por idioma del turno)
        greetings = {"hola", "buenas", "hello", "hi", "hey"}
        if original_question.lower() in greetings:
            answer = (
                "¡Hola! ¿En qué puedo ayudarte hoy?"
                if turn_lang == "es"
                else "Hi! How can I help you today?"
            )
            save_history(client_id, session_id, "user", original_question, channel="chat")
            save_history(client_id, session_id, "assistant", answer, channel="chat")
            return answer

        # =====================================================
        # 🚀 Modo directo (sin RAG)
        # =====================================================
        if disable_rag:
            logging.info("🧠 RAG disabled — using direct mode.")
            llm_direct = ChatOpenAI(temperature=temperature)

            system_direct = SystemMessage(
                content=f"""
{prompt.strip() if prompt else ''}

Rules:
- Respond in {"Spanish" if turn_lang == "es" else "English"}.
- Be concise, professional, and helpful.
""".strip()
            )

            resp = llm_direct.invoke([
                system_direct,
                HumanMessage(content=original_question)
            ])
            answer = (resp.content or "").strip() or fallback

            save_history(client_id, session_id, "user", original_question, channel="chat")
            save_history(client_id, session_id, "assistant", answer, channel="chat")
            return answer

        # =====================================================
        # 📂 Vectorstore (YA INGESTADO)
        # =====================================================
        logging.info(f"📂 Cargando vectorstore para cliente {client_id}...")

        client_data_path = os.path.abspath(f"./chroma_{client_id}")
        logging.info(f"📂 Vectorstore path (aligned with indexer): {client_data_path}")


        # 🛡️ Si no existe vectorstore, no podemos hacer RAG
        if not os.path.exists(client_data_path):
            logging.warning("⚠️ Vectorstore no encontrado para el cliente.")
            save_history(client_id, session_id, "user", original_question, channel="chat")
            save_history(client_id, session_id, "assistant", fallback, channel="chat")
            return fallback


        # =====================================================
        # 🈶 Idioma del corpus (YA CALCULADO EN INGESTIÓN)
        # =====================================================
        # 👉 Idealmente viene de client_settings.corpus_language
        corpus_lang = get_language_for_client(client_id)  # fallback seguro
        logging.info(f"🈶 Idioma del corpus (persistido): {corpus_lang}")


        # =====================================================
        # 🌍 Traducción SOLO para retrieval (si aplica)
        # =====================================================
        retrieval_question = original_question
        if corpus_lang in ("es", "en") and corpus_lang != turn_lang:
            retrieval_question = _translate_text(original_question, corpus_lang)


        # =====================================================
        # ✏️ Rewrite para retrieval
        # =====================================================
        rewritten_question = _rewrite_for_retrieval(
            conversation_memory,
            retrieval_question
        )


        # =====================================================
        # 🔍 Recuperación (SIN re-embeddings)
        # =====================================================
        vectordb = Chroma(
            persist_directory=client_data_path,
            embedding_function=OpenAIEmbeddings(),
            collection_name=client_id
        )

        retriever = vectordb.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 20, "lambda_mult": 0.5}
        )

        retrieved_docs = retriever.invoke(rewritten_question)

        if not retrieved_docs:
            save_history(client_id, session_id, "user", original_question, channel="chat")
            save_history(client_id, session_id, "assistant", fallback, channel="chat")
            return fallback


        # =====================================================
        # 🧩 Construir contexto
        # =====================================================
        MAX_CHARS = 9000
        context_text, total = "", 0

        for d in retrieved_docs:
            text = (d.page_content or "").strip()
            if not text:
                continue

            remaining = MAX_CHARS - total
            context_text += text[:remaining] + "\n\n"
            total += len(text)

            if total >= MAX_CHARS:
                break

        sources = list({d.metadata.get("source", "unknown") for d in retrieved_docs})


        # =====================================================
        # 🧱 System Prompt FINAL
        # =====================================================
        language_rule = (
            "Responde SIEMPRE en español."
            if turn_lang == "es"
            else "Always respond in English."
        )

        system_prompt = f"""
        You are a helpful AI assistant representative of this business that answers questions ONLY with the information provided by the business.

        {prompt.strip() if prompt else ''}

        Core Rules:
        - You MUST use ONLY the information provided.
        - If the answer is not clearly found, reply exactly: "{fallback}"
        - Never use external knowledge.
        - {language_rule}
        - Never mention the words "context" or "document".
        """.strip()

        human_prompt = f"""
        <conversation>
        {conversation_memory}
        </conversation>

        <information>
        {context_text}
        </information>

        <question>
        {original_question}
        </question>
        """.strip()


        llm = ChatOpenAI(
            model=DEFAULT_CHAT_MODEL,
            temperature=temperature
        )

        raw = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        answer = (raw.content or "").strip() or fallback


        # =====================================================
        # 🛡️ Anti-hallucination (solo si idioma coincide)
        # =====================================================

        logging.info("🧪 CONTEXT PREVIEW:")
        logging.info(context_text[:500])

        logging.info("🧪 RAW ANSWER PREVIEW:")
        logging.info(answer)

        if corpus_lang == turn_lang:
            keywords = [w.lower() for w in context_text.split()[:80]]
            if answer != fallback and not any(k in answer.lower() for k in keywords):
                answer = fallback


        if show_sources and answer != fallback and sources:
            answer += "\n\nSources: " + ", ".join(sources)

        # =====================================================
        # =====================================================
        # 💾 Guardar historial
        # =====================================================
        save_history(client_id, session_id, "user", original_question, channel="chat")
        save_history(client_id, session_id, "assistant", answer, channel="chat")

        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")
        return answer

    except Exception as e:
        logging.exception(
            f"❌ Error inesperado procesando pregunta para client_id={client_id}: {e}"
        )

        return (
            "Ups, ocurrió un problema inesperado. Por favor intenta de nuevo."
            if FALLBACK_BY_LANG.get("es")
            else "Oops, something went wrong. Please try again."
        )

# ------------------------------------------------------------------
# 🔁 Alias de compatibilidad para canales externos (WhatsApp, Email)
# NO rompe widget ni flujos existentes
# ------------------------------------------------------------------

async def handle_message(
    client_id: str,
    session_id: str,
    user_message: str,
    channel: str = "chat"
) -> str:
    result = ask_question(
        messages=user_message,
        client_id=client_id,
        session_id=session_id
    )

    # 🛡️ Blindaje total: si es coroutine, la resolvemos
    if hasattr(result, "__await__"):
        result = await result

    return str(result)