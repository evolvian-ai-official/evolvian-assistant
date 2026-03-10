"""
BASE5 - Evolvian RAG Final (seguro, flexible y anti-hallucination)
✅ FIX: idioma consistente + system role real + no contaminar question original
"""

import os
import logging

from typing import Any, List, Dict, Optional, Union
import uuid
import re
import unicodedata
from api.config.config import DEFAULT_CHAT_MODEL
from api.utils.paths import get_base_data_path


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

LIMIT_OR_NO_DOCS_FALLBACK = {
    "es": (
        "Ahora mismo no puedo responder nuevas preguntas.\n\n"
        "Intenta más tarde o ponte en contacto con nuestro equipo directamente "
        "para obtener más información. Estaré aquí para ayudarte cuando el servicio "
        "esté disponible nuevamente."
    ),
    "en": (
        "I can’t answer new questions right now.\n\n"
        "Please try again later or contact our team directly "
        "for more information. I’ll be here to help you when the service "
        "is available again."
    ),
}



FALLBACK_BY_LANG = {
    "es": "No tengo información para responder esta pregunta.Si tienes una duda relacionada con este negocio y necesitas más detalle, puedes contactarnos directamente. Mientras tanto, con gusto puedo ayudarte con cualquier otra pregunta.",
    "en": "I don’t have information to answer this question. If you have a question related to this business and need more details, you can contact us directly. In the meantime, I’m happy to help with any other question.",
}





def _normalize_for_lang_detection(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return (
        without_marks.replace("’", "'")
        .replace("`", "'")
        .replace("´", "'")
        .lower()
    )


def _guess_lang_es_en(text: str) -> Optional[str]:
    """
    Heurística rápida y robusta para detectar ES / EN en mensajes cortos.
    Devuelve:
    - "es" / "en" cuando hay evidencia razonable
    - None cuando el texto es ambiguo
    """
    original = (text or "").strip()
    if not original:
        return None

    t = _normalize_for_lang_detection(original)
    if not t:
        return None

    # 1️⃣ Señales fuertes de español
    if any(c in original for c in "¿¡ñáéíóúÁÉÍÓÚÑ"):
        return "es"

    tokens = re.findall(r"[a-zA-Z']+", t)
    if not tokens:
        return None

    es_words_strong = {
        "hola", "buenas", "gracias", "quiero", "necesito", "tengo", "tienes",
        "informacion", "servicios", "precio", "cita", "horario", "horarios",
        "veterinaria", "puedes", "ayuda", "donde", "cuando", "como", "porque",
    }
    es_words_common = {
        "de", "la", "el", "los", "las", "un", "una", "que", "para", "por",
        "con", "del", "al", "en", "y", "se", "su",
    }
    en_words = {
        "the", "and", "is", "are", "do", "does", "can", "could", "would",
        "should", "please", "about", "have", "has", "what", "which", "where",
        "when", "why", "how", "you", "your",
    }

    es_score = 0
    en_score = 0
    for tok in tokens:
        if tok in es_words_strong:
            es_score += 2
        elif tok in es_words_common:
            es_score += 1
        if tok in en_words:
            en_score += 2

    # 2️⃣ Decisión por puntaje
    if es_score >= 2 and es_score > en_score:
        return "es"
    if en_score >= 2 and en_score > es_score:
        return "en"

    # 3️⃣ Frases cortas comunes
    if t.startswith(("hola", "buenas", "gracias")):
        return "es"
    if t.startswith(("hi", "hello", "thanks")):
        return "en"

    # 4️⃣ Ambiguo -> None para usar fallbacks más estables
    return None


def _client_language_fallback(client_id: str) -> Optional[str]:
    client_lang = (get_language_for_client(client_id) or "").strip().lower()
    if client_lang.startswith("es"):
        return "es"
    if client_lang.startswith("en"):
        return "en"
    return None


def _resolve_user_language(client_id: str, user_text: str) -> str:
    """
    Decide el idioma del turno según el MENSAJE del usuario.
    El idioma del cliente actúa como fallback cuando el texto es ambiguo.

    Prioridad:
    1) Heurística ES/EN sobre el mensaje (si hay evidencia)
    2) langdetect (opcional)
    3) client_settings.language
    4) fallback 'en'
    """

    # 1️⃣ Heurística rápida (inputs cortos, chats)
    heuristic = _guess_lang_es_en(user_text)
    if heuristic in ("es", "en"):
        return heuristic

    # 2️⃣ Detección probabilística (backup, puede fallar en textos muy cortos)
    detected = _safe_langdetect(user_text)
    if detected in ("es", "en"):
        return detected

    # 3️⃣ Idioma configurado del cliente (fallback estable)
    client_lang = _client_language_fallback(client_id)
    if client_lang:
        return client_lang

    # 4️⃣ Último fallback
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
    if detected_lang and detected_lang == target_lang:
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

def _has_active_documents(client_id: str) -> bool:
    """
    Fuente de verdad:
    Retorna True SOLO si el cliente tiene documentos activos.
    """
    from api.config.config import supabase

    res = (
        supabase
        .table("document_metadata")
        .select("id")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    return bool(res.data)


def _get_active_storage_paths(client_id: str) -> set[str]:
    """Devuelve rutas activas para reforzar aislamiento de documentos vigentes."""
    from api.config.config import supabase

    res = (
        supabase
        .table("document_metadata")
        .select("storage_path")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )
    rows = res.data or []
    return {
        str(row.get("storage_path") or "").strip()
        for row in rows
        if str(row.get("storage_path") or "").strip()
    }


def ask_question(
    messages: Union[List[Dict[str, str]], str],
    client_id: str,
    session_id: str = None,
    disable_rag: bool = False,
    channel: str = "chat",
    provider: str = "internal",
    return_metadata: bool = False,
    persist_history: bool = True,
) -> Union[str, Dict[str, Any]]:
    try:
        session_id = session_id or str(uuid.uuid4())

        def _result(
            answer_text: str,
            confidence_score: float = 0.9,
            handoff_recommended: Optional[bool] = None,
            handoff_reason: Optional[str] = None,
            confidence_reason: Optional[str] = None,
        ) -> Union[str, Dict[str, Any]]:
            try:
                confidence = float(confidence_score)
            except Exception:
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))
            if handoff_recommended is None:
                handoff_recommended = confidence < 0.35
            if handoff_recommended and not handoff_reason:
                handoff_reason = "low_confidence"
            payload: Dict[str, Any] = {
                "answer": str(answer_text or ""),
                "confidence_score": confidence,
                "handoff_recommended": bool(handoff_recommended),
                "human_intervention_recommended": bool(handoff_recommended),
                "needs_human": bool(handoff_recommended),
                "handoff_reason": handoff_reason,
                "confidence_reason": confidence_reason,
            }
            return payload if return_metadata else payload["answer"]

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
            return _result(
                "No logré entender tu mensaje ¿Podrías intentarlo de nuevo?",
                confidence_score=0.25,
                handoff_recommended=False,
                confidence_reason="empty_or_unparseable_question",
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
            if persist_history:
                save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
                save_history(client_id, session_id, "assistant", answer, channel=channel, provider=provider)

            return _result(answer, confidence_score=0.98, handoff_recommended=False, confidence_reason="greeting")

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

           
            if persist_history:
                save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
                save_history(client_id, session_id, "assistant", answer, channel=channel, provider=provider)

            return _result(answer, confidence_score=0.8, handoff_recommended=False, confidence_reason="direct_mode")





        # =====================================================
        # 📂 Vectorstore loading (RAG SAFE)
        # =====================================================

        logging.info(f"📂 Preparing RAG vectorstore for client {client_id}...")

        # -----------------------------------------------------
        # 🛡️ 1) Fuente de verdad → documentos activos
        # -----------------------------------------------------
        if not _has_active_documents(client_id):
            fallback_limit = LIMIT_OR_NO_DOCS_FALLBACK.get(turn_lang, LIMIT_OR_NO_DOCS_FALLBACK["en"])

            if persist_history:
                save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
                save_history(client_id, session_id, "assistant", fallback_limit, channel=channel, provider=provider)
            return _result(
                fallback_limit,
                confidence_score=0.05,
                handoff_recommended=True,
                handoff_reason="no_active_documents",
                confidence_reason="no_active_documents",
            )



        # -----------------------------------------------------
        # 🗂️ 2) Resolver path de vectorstore
        # -----------------------------------------------------
        base_path = get_base_data_path()
        client_data_path = os.path.join(base_path, f"chroma_{client_id}")

        logging.info(
            f"📂 Vectorstore path resolved (aligned with indexer): {client_data_path}"
        )


        # -----------------------------------------------------
        # 🛡️ 3) Cache check → si no existe, NO RAG
        # -----------------------------------------------------
        if not os.path.exists(client_data_path):
            fallback_limit = LIMIT_OR_NO_DOCS_FALLBACK.get(turn_lang, LIMIT_OR_NO_DOCS_FALLBACK["en"])

            if persist_history:
                save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
                save_history(client_id, session_id, "assistant", fallback_limit, channel=channel, provider=provider)
            return _result(
                fallback_limit,
                confidence_score=0.05,
                handoff_recommended=True,
                handoff_reason="vectorstore_unavailable",
                confidence_reason="vectorstore_missing",
            )



        # -----------------------------------------------------
        # ✅ 4) Vectorstore listo para usarse
        # -----------------------------------------------------
        logging.info(
            f"✅ Vectorstore ready for client {client_id}. Proceeding with retrieval."
        )





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

        # Refuerzo: usar solo chunks asociados a documentos activos cuando exista metadata.
        active_storage_paths = _get_active_storage_paths(client_id)
        docs_with_storage_meta = [
            d for d in retrieved_docs
            if isinstance(getattr(d, "metadata", None), dict) and d.metadata.get("storage_path")
        ]
        if docs_with_storage_meta:
            retrieved_docs = [
                d for d in docs_with_storage_meta
                if str(d.metadata.get("storage_path")).strip() in active_storage_paths
            ]

        if not retrieved_docs:
            if persist_history:
                save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
                save_history(client_id, session_id, "assistant", fallback, channel=channel, provider=provider)
            return _result(
                fallback,
                confidence_score=0.2,
                handoff_recommended=True,
                handoff_reason="no_retrieval_match",
                confidence_reason="retriever_returned_no_docs",
            )


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

        anti_hallucination_fallback = False
        if corpus_lang == turn_lang:
            keywords = [w.lower() for w in context_text.split()[:80]]
            if answer != fallback and not any(k in answer.lower() for k in keywords):
                answer = fallback
                anti_hallucination_fallback = True


        if show_sources and answer != fallback and sources:
            answer += "\n\nSources: " + ", ".join(sources)

        # =====================================================
        # =====================================================
        # 💾 Guardar historial
        # =====================================================
        if persist_history:
            save_history(client_id, session_id, "user", original_question, channel=channel, provider=provider)
            save_history(client_id, session_id, "assistant", answer, channel=channel, provider=provider)

        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")
        if answer == fallback:
            return _result(
                answer,
                confidence_score=0.15 if anti_hallucination_fallback else 0.22,
                handoff_recommended=True,
                handoff_reason="low_confidence",
                confidence_reason=(
                    "anti_hallucination_fallback"
                    if anti_hallucination_fallback
                    else "rag_fallback_response"
                ),
            )
        return _result(
            answer,
            confidence_score=0.82,
            handoff_recommended=False,
            confidence_reason="rag_answer_with_retrieval",
        )

    except Exception as e:
        logging.exception(
            f"❌ Error inesperado procesando pregunta para client_id={client_id}: {e}"
        )

        return _result(
            (
                "Ups, ocurrió un problema inesperado. Por favor intenta de nuevo."
                if FALLBACK_BY_LANG.get("es")
                else "Oops, something went wrong. Please try again."
            ),
            confidence_score=0.0,
            handoff_recommended=True,
            handoff_reason="processing_error",
            confidence_reason="rag_pipeline_exception",
        )

# ------------------------------------------------------------------
# 🔁 Alias de compatibilidad para canales externos (WhatsApp, Email)
# NO rompe widget ni flujos existentes
# ------------------------------------------------------------------


async def handle_message(
    client_id: str,
    session_id: str,
    user_message: str,
    channel: str = "chat",
    provider: str = "internal",
) -> Optional[str]:
    from api.modules.assistant_rag.intent_router import process_user_message

    result = process_user_message(
        client_id=client_id,
        session_id=session_id,
        message=user_message,
        channel=channel,
        provider=provider,
    )

    if hasattr(result, "__await__"):
        result = await result

    if result is None:
        return None

    return str(result)
