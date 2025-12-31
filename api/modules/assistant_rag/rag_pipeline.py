"""
BASE5 - Evolvian RAG Final (seguro, flexible y anti-hallucination)
✅ FIX: idioma consistente + system role real + no contaminar question original
"""

import os
import logging
import requests
from tempfile import NamedTemporaryFile
from typing import List, Dict, Optional, Union
import uuid

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma

from langchain_core.messages import SystemMessage, HumanMessage

from api.modules.assistant_rag.supabase_client import (
    save_history,
    list_documents_with_signed_urls,
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
    "es": "No tengo información para responder esta pregunta.",
    "en": "I do not have information for this question.",
}


def get_base_data_path() -> str:
    render_root = "/opt/render/project/src"
    base_dir = os.path.join(render_root, "data") if os.path.exists(render_root) else os.path.join(os.getcwd(), "data")
    os.makedirs(base_dir, exist_ok=True)
    logging.info(f"📂 Base data path usada: {base_dir}")
    return base_dir


def load_document(file_path: str) -> List:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path)
    else:
        raise ValueError(f"Formato de archivo no soportado: {ext}")
    return loader.load()


def chunk_documents(documents: List) -> List:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    return splitter.split_documents(documents)


def fetch_signed_documents(client_id: str) -> List[str]:
    try:
        res = list_documents_with_signed_urls(client_id)
        if not res:
            logging.info("📂 No hay documentos firmados disponibles.")
            return []
        urls = [doc["signed_url"] for doc in res if doc.get("signed_url")]
        filenames = [url.split("/")[-1].split("?")[0] for url in urls]
        logging.info(f"📂 Documentos firmados encontrados: {len(filenames)} → {filenames}")
        return urls
    except Exception as e:
        logging.error(f"❌ Error al obtener documentos firmados: {e}")
        return []


def _guess_lang_es_en(text: str) -> str:
    """
    Heurística rápida para ES/EN (mejor que langdetect en inputs cortos).
    """
    t = (text or "").strip().lower()
    if not t:
        return "en"

    # señales fuertes ES
    if any(c in t for c in "¿¡ñáéíóú"):
        return "es"

    # stopwords/indicadores ES típicos (incluye variantes)
    es_words = {
        "hola", "buenas", "donde", "dónde", "como", "cómo", "cuanto", "cuánto",
        "precio", "planes", "informacion", "información", "inscribo", "inscribir",
        "registro", "registrar", "ayuda", "soporte", "quiero", "necesito", "horario",
        "cita", "citas", "disponibilidad"
    }
    tokens = set(t.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "").split())
    if tokens.intersection(es_words):
        return "es"

    return "en"


def _safe_langdetect(text: str) -> Optional[str]:
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return None


def _resolve_user_language(client_id: str, user_text: str) -> str:
    """
    Prioridad:
    1) client_settings.language (si viene 'es' o 'en' lo respetamos)
    2) heurística ES/EN
    3) langdetect (opcional)
    4) fallback 'en'
    """
    client_lang = (get_language_for_client(client_id) or "").strip().lower()
    if client_lang.startswith("es"):
        return "es"
    if client_lang.startswith("en"):
        return "en"

    heuristic = _guess_lang_es_en(user_text)
    if heuristic in ("es", "en"):
        return heuristic

    detected = _safe_langdetect(user_text)
    if detected in ("es", "en"):
        return detected

    return "en"


def _detect_corpus_language(chunks: List) -> Optional[str]:
    try:
        sample_text = "\n".join(c.page_content for c in chunks[:3] if getattr(c, "page_content", None))
        if not sample_text.strip():
            return None
        detected = _safe_langdetect(sample_text)
        return detected
    except Exception:
        return None


def _translate_text(text: str, target_lang: str) -> str:
    """
    Traduce SOLO para retrieval. No tocar idioma de salida final.
    target_lang: 'es' | 'en' | etc.
    """
    if not text.strip():
        return text

    llm_tr = ChatOpenAI(temperature=0)
    target_name = "Spanish" if target_lang == "es" else "English" if target_lang == "en" else target_lang

    sys = SystemMessage(content="You are a translation engine. Follow instructions exactly.")
    hum = HumanMessage(content=f"Translate the text to {target_name}. Return ONLY the translated text.\n\nText:\n{text}")
    resp = llm_tr.invoke([sys, hum])
    out = (resp.content or "").strip()
    return out or text


def _rewrite_for_retrieval(conversation_memory: str, retrieval_question: str, target_lang: str) -> str:
    """
    Reescritura SOLO para retrieval. Puede ser en el idioma del corpus si así lo pasas.
    """
    llm_rw = ChatOpenAI(temperature=0)

    # Prompt en el mismo idioma del retrieval_question (mejor para embedding / búsqueda)
    if target_lang == "es":
        prompt = f"""Reescribe la pregunta del usuario como una pregunta clara y autocontenida, usando solo el contexto de la conversación.
Si no estás seguro, devuélvela sin cambios.

Conversación:
{conversation_memory}

Pregunta:
{retrieval_question}
"""
    else:
        prompt = f"""Rewrite the user's question into a clear, standalone version using only the context of this conversation.
If unsure, return the question unchanged.

Conversation:
{conversation_memory}

User question:
{retrieval_question}
"""
    sys = SystemMessage(content="You rewrite questions for retrieval. Do not add new facts.")
    hum = HumanMessage(content=prompt)
    resp = llm_rw.invoke([sys, hum])
    out = (resp.content or "").strip()
    return out or retrieval_question


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
                {"role": (m.get("role", "user") or "user").strip(),
                 "content": (m.get("content") or "").strip()}
                for m in messages if m.get("content")
            ]
        else:
            norm_messages = [{"role": "user", "content": str(messages).strip()}]

        last_user_msg = next((m for m in reversed(norm_messages) if m["role"] == "user"), None)
        question = (last_user_msg["content"] if last_user_msg else "").strip()
        if not question:
            return "No se recibió ningún mensaje válido."

        # ✅ Guardar original SIEMPRE
        original_question = question

        convo_tail = norm_messages[-10:]
        conversation_memory = "\n".join(
            f"{'User' if m['role']=='user' else 'Assistant'}: {m.get('content','').strip()}"
            for m in convo_tail
        )

        user_lang = _resolve_user_language(client_id, original_question)
        fallback = FALLBACK_BY_LANG.get(user_lang, FALLBACK_BY_LANG["en"])

        logging.info(f"🧩 Pregunta procesada: {original_question}")
        logging.info(f"🈶 Idioma usuario (final): {user_lang}")

        # 👋 Saludo rápido
        greetings_es = {"hola", "buenas", "hey"}
        greetings_en = {"hello", "hi", "hey"}
        if original_question.lower() in greetings_es or original_question.lower() in greetings_en:
            save_history(client_id, session_id, "user", original_question, channel="chat")
            answer = "Hi! How can I help you today?" if original_question.lower() in greetings_en else "¡Hola! ¿En qué puedo ayudarte hoy?"
            save_history(client_id, session_id, "assistant", answer, channel="chat")
            return answer

        # =====================================================
        # 🚀 Modo directo (sin RAG)
        # =====================================================
        if disable_rag:
            logging.info("🧠 RAG disabled — using direct mode.")
            try:
                llm_direct = ChatOpenAI(temperature=temperature)

                system_direct = SystemMessage(content=f"""
{prompt.strip() if prompt else ''}

Rules:
- Respond in {"Spanish" if user_lang=="es" else "English"}.
- Be concise, professional, and helpful.
""".strip())

                human_direct = HumanMessage(content=original_question)
                resp = llm_direct.invoke([system_direct, human_direct])
                answer = (resp.content or "").strip() or fallback

                save_history(client_id, session_id, "user", original_question, channel="chat")
                save_history(client_id, session_id, "assistant", answer, channel="chat")
                return answer
            except Exception as e:
                logging.error(f"⚠️ Error executing direct chat mode: {e}")
                # fallback a RAG normal si falla

        # =====================================================
        # 📂 Documentos
        # =====================================================
        logging.info(f"📂 Buscando documentos para cliente {client_id}...")
        signed_urls = fetch_signed_documents(client_id)
        if not signed_urls:
            msg = "No se encontraron documentos asociados a este asistente." if user_lang == "es" else "No documents are associated with this assistant."
            return msg

        # 📑 Descargar y trocear
        all_chunks, used_docs = [], []
        for url in signed_urls:
            try:
                filename = url.split("/")[-1].split("?")[0]
                resp = requests.get(url, timeout=15)
                if resp.status_code != 200:
                    continue

                suffix = ".pdf" if filename.lower().endswith(".pdf") else ".txt"
                with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(resp.content)
                    tmp_file.flush()

                    docs = load_document(tmp_file.name)
                    chunks = chunk_documents(docs)

                    for ch in chunks:
                        ch.metadata["source"] = filename
                        ch.metadata["tenant_id"] = client_id

                    all_chunks.extend(chunks)
                    used_docs.append(filename)

                logging.info(f"✂️ {filename} → {len(chunks)} chunks")
            except Exception as e:
                logging.warning(f"❌ Error procesando {url}: {e}")

        if not all_chunks:
            return "No hay contenido disponible para generar una respuesta." if user_lang == "es" else "No content is available to generate an answer."

        # =====================================================
        # 🈶 Idioma del corpus (solo para retrieval)
        # =====================================================
        corpus_lang = _detect_corpus_language(all_chunks)
        logging.info(f"🈶 Idioma corpus detectado: {corpus_lang}")

        # ✅ SOLO para retrieval: traducir si difiere
        retrieval_question = original_question
        if corpus_lang and corpus_lang in ("es", "en") and corpus_lang != user_lang:
            retrieval_question = _translate_text(original_question, corpus_lang)
            logging.info(f"🌍 Retrieval question traducida a {corpus_lang}: {retrieval_question}")

        # ✏️ Reescritura SOLO para retrieval
        rewritten_question = _rewrite_for_retrieval(conversation_memory, retrieval_question, corpus_lang or user_lang)

        # =====================================================
        # 🔍 Recuperación
        # =====================================================
        BASE_DATA_DIR = get_base_data_path()
        client_data_path = os.path.join(BASE_DATA_DIR, client_id)
        os.makedirs(client_data_path, exist_ok=True)

        embeddings = OpenAIEmbeddings()
        vectordb = Chroma.from_documents(
            all_chunks,
            embeddings,
            persist_directory=client_data_path,
            collection_name=client_id
        )

        retriever = vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 20, "lambda_mult": 0.5})
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
            t = (d.page_content or "").strip()
            if not t:
                continue
            length = min(len(t), MAX_CHARS - total)
            context_text += t[:length] + "\n\n"
            total += length
            if total >= MAX_CHARS:
                break

        sources = list({d.metadata.get("source", "unknown") for d in retrieved_docs})

        # =====================================================
        # 🧱 System Prompt REAL (SystemMessage)
        # =====================================================
        language_rule = "Responde SIEMPRE en español." if user_lang == "es" else "Always respond in English."

        system_prompt = f"""
You are Evolvian, a professional AI assistant trained ONLY on your client's uploaded documents.

{prompt.strip() if prompt else ''}

Core Rules:
- You MUST use ONLY the information provided in the context.
- If the answer is not clearly found there, reply exactly: "{fallback}"
- Never use external knowledge or general facts.
- {language_rule}
- Never mention the words "context" or "document" in your reply.
""".strip()

        # Mensaje humano con conversación+contexto+pregunta ORIGINAL
        human_prompt = f"""
<conversation>
{conversation_memory}
</conversation>

<context>
{context_text}
</context>

<question>
{original_question}
</question>
""".strip()

        llm = ChatOpenAI(temperature=temperature)
        raw = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
        answer = (raw.content or "").strip() or fallback

        # =====================================================
        # 🛡️ Anti-hallucination (con fallback por idioma)
        # =====================================================
        # Heurística simple: si no hay overlap mínimo con el contexto, cae a fallback.
        # (Puedes mejorar luego con verificación por citas o similarity scoring)
        context_keywords = [w.lower() for w in context_text.split()[:80]]
        if (
            answer != fallback
            and not any(k in answer.lower() for k in context_keywords)
        ):
            answer = fallback

        if show_sources and answer != fallback and sources:
            answer += "\n\nSources: " + ", ".join(sources)

        # 💾 Guardar historial (SIEMPRE con original_question)
        save_history(client_id, session_id, "user", original_question, channel="chat")
        save_history(client_id, session_id, "assistant", answer, channel="chat")

        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")
        return answer

    except Exception as e:
        logging.exception(f"❌ Error inesperado procesando pregunta para {client_id}: {e}")
        return "Error: ocurrió un problema inesperado al procesar tu pregunta."
