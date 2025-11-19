"""BASE5 - Evolvian RAG Final (seguro, flexible y anti-hallucination)"""

import os
import logging
import requests
from tempfile import NamedTemporaryFile
from typing import List, Dict
import uuid

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma

from api.modules.assistant_rag.supabase_client import (
    save_history,
    list_documents_with_signed_urls,
)
from api.modules.assistant_rag.prompt_utils import (
    get_prompt_for_client,
    get_temperature_for_client,
)

# 🚫 Desactivar telemetría de Chroma
os.environ["ANONYMIZED_TELEMETRY"] = "false"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# 🧩 Ruta segura compatible con local y Render
def get_base_data_path():
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


def ask_question(
    messages: List[Dict[str, str]] | str,
    client_id: str,
    session_id: str = None,
    disable_rag: bool = False  # 👈 NUEVO parámetro opcional
) -> str:
    try:
        session_id = session_id or str(uuid.uuid4())
        prompt = get_prompt_for_client(client_id)
        temperature = get_temperature_for_client(client_id)
        show_sources = os.getenv("EVOLVIAN_SHOW_SOURCES", "false").lower() == "true"

        # 🔧 Normalizar mensajes
        if isinstance(messages, list):
            norm_messages = [
                {"role": m.get("role", "user").strip(), "content": (m.get("content") or "").strip()}
                for m in messages if m.get("content")
            ]
        else:
            norm_messages = [{"role": "user", "content": str(messages).strip()}]

        last_user_msg = next((m for m in reversed(norm_messages) if m["role"] == "user"), None)
        question = (last_user_msg["content"] if last_user_msg else "").strip()
        if not question:
            return "No se recibió ningún mensaje válido."

        convo_tail = norm_messages[-10:]
        logging.info(f"🧩 Pregunta procesada: {question}")

        # =====================================================
        # 🚀 NUEVO: modo directo (sin RAG) — usado por calendario o email
        # =====================================================
        if disable_rag:
            logging.info("🧠 RAG disabled — using direct system prompt only.")
            try:
                from api.modules.assistant_rag.llm import openai_chat
                messages_payload = [
                    {"role": "system", "content": prompt or "You are Evolvian Assistant."},
                    {"role": "user", "content": question}
                ]
                response = openai_chat(messages_payload, temperature=temperature)
                logging.info(f"✅ Direct mode response generated successfully.")
                return response
            except Exception as e:
                logging.error(f"⚠️ Error executing direct chat mode: {e}")
                # fallback a RAG normal si falla
                disable_rag = False

        # =====================================================
        # 🌍 Language detection (English as default, but respect user input)
        # =====================================================
        try:
            from langdetect import detect
            detected_lang = detect(question)
            logging.info(f"🌍 Detected language (langdetect): {detected_lang}")
        except Exception as e:
            logging.warning(f"⚠️ Language detection failed: {e}")
            detected_lang = None

        # 🔠 Keyword-based correction (avoid false "en" detections)
        common_spanish_words = [
            "hola", "buenas", "diferencia", "planes", "precio", "documento", "mensaje",
            "ayuda", "soporte", "cuánto", "tienes", "quiero", "información"
        ]

        if any(word in question.lower() for word in common_spanish_words):
            user_lang = "es"
        elif detected_lang in ["en", "es", "fr", "de", "pt", "it"]:
            user_lang = detected_lang
        else:
            user_lang = "en"  # Fallback seguro

        if not user_lang or user_lang.strip() == "":
            user_lang = "en"

        language_instruction = (
            "Responde siempre en español."
            if user_lang == "es"
            else "Always respond in English."
        )
        logging.info(f"🈶 Idioma final del usuario: {user_lang}")

        # 👋 Saludo rápido
        greetings_es = {"hola", "buenas", "hey"}
        greetings_en = {"hello", "hi", "hey"}
        if question.lower() in greetings_es or question.lower() in greetings_en:
            save_history(client_id, session_id, "user", question, channel="chat")
            answer = "Hi! How can I help you today?" if question.lower() in greetings_en else "¡Hola! ¿En qué puedo ayudarte hoy?"
            save_history(client_id, session_id, "assistant", answer, channel="chat")
            return answer

        # 📂 Documentos
        logging.info(f"📂 Buscando documentos para cliente {client_id}...")
        signed_urls = fetch_signed_documents(client_id)
        if not signed_urls:
            return "No se encontraron documentos asociados a este asistente." if user_lang != "en" else \
                   "No documents are associated with this assistant."

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
            return "No hay contenido disponible para generar una respuesta."

        # 🧠 Memoria conversacional
        conversation_memory = "\n".join(
            f"{'User' if m['role']=='user' else 'Assistant'}: {m.get('content','').strip()}"
            for m in convo_tail
        )

        # 🈶 Idioma del corpus
        try:
            sample_text = "\n".join(c.page_content for c in all_chunks[:3])
            from langdetect import detect as detect_lang
            corpus_lang = detect_lang(sample_text) if sample_text.strip() else None
        except Exception:
            corpus_lang = None
        logging.info(f"🈶 Idioma usuario={user_lang} | corpus={corpus_lang}")

        # 🌐 Traducción proactiva si difieren
        if corpus_lang and user_lang != corpus_lang:
            try:
                llm_tr = ChatOpenAI(temperature=0)
                tr_prompt = f"Translate this question to {corpus_lang.upper()} ONLY:\n{question}"
                tr_resp = llm_tr.invoke(tr_prompt)
                translated_q = (tr_resp.content or "").strip()
                if translated_q:
                    logging.info(f"🌍 Pregunta traducida automáticamente: {translated_q}")
                    question = translated_q
            except Exception as e:
                logging.warning(f"⚠️ No se pudo traducir la pregunta: {e}")

        # ✏️ Reescritura
        try:
            llm_rewriter = ChatOpenAI(temperature=0)
            rewrite_prompt = f"""Rewrite the user's question into a clear, standalone version using only the context of this conversation.
If unsure, return the question unchanged.

Conversation:
{conversation_memory}

User question:
{question}"""
            rewrite_resp = llm_rewriter.invoke(rewrite_prompt)
            rewritten_question = (rewrite_resp.content or "").strip() or question
        except Exception as e:
            logging.warning(f"ℹ️ Rewriter no disponible: {e}")
            rewritten_question = question

        # 🔍 Recuperación
        BASE_DATA_DIR = get_base_data_path()
        client_data_path = os.path.join(BASE_DATA_DIR, client_id)
        os.makedirs(client_data_path, exist_ok=True)
        embeddings = OpenAIEmbeddings()
        vectordb = Chroma.from_documents(all_chunks, embeddings, persist_directory=client_data_path, collection_name=client_id)
        retriever = vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 20, "lambda_mult": 0.5})
        retrieved_docs = retriever.invoke(rewritten_question)

        if not retrieved_docs:
            fallback = "I do not have information for this question."
            save_history(client_id, session_id, "assistant", fallback, channel="chat")
            return fallback

        # 🧩 Contexto
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

        # 🧱 Prompt con anti-hallucinations
        system_prompt = f"""
You are Evolvian, a professional AI assistant trained ONLY on your client's uploaded documents.

{prompt.strip() if prompt else ''}

Core Rules:
- You MUST use ONLY the information inside <context>.
- If the answer is not clearly found there, reply exactly: "I do not have information for this question."
- Never use external knowledge or general facts.
- Always respond naturally and professionally in the user's language.

### Important Rules
1. Base your answer **strictly** on the content inside <context></context>.
2. If the answer is not clearly in context, say exactly:
   "I do not have information for this question."
3. If the question is broad (e.g., "tell me more" or "can you explain further"), summarize the most relevant ideas.
4. If the question is yes/no type, answer naturally (“Yes, according to the document...”) but always justify with evidence from context.
5. Never mention the words "context" or "document" in your reply.
"""

        # 🧠 Prompt final
        base_prompt = f"""
{system_prompt}

<conversation>
{conversation_memory}
</conversation>

<context>
{context_text}
</context>

<question>
{question}
</question>

{language_instruction}
"""

        llm = ChatOpenAI(temperature=temperature)
        raw = llm.invoke(base_prompt)
        answer = (raw.content or "").strip() if hasattr(raw, "content") else str(raw).strip()

        fallback = "I do not have information for this question."

        # 🛡️ Anti-hallucination: si el modelo responde fuera de contexto
        context_keywords = [w.lower() for w in context_text.split()[:50]]
        if (
            not any(k in answer.lower() for k in context_keywords)
            and "i do not have information" not in answer.lower()
        ):
            answer = fallback

        if show_sources and answer != fallback and sources:
            answer += "\n\nSources: " + ", ".join(sources)

        # 💾 Guardar historial
        save_history(client_id, session_id, "user", question, channel="chat")
        save_history(client_id, session_id, "assistant", answer, channel="chat")

        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")
        return answer

    except Exception as e:
        logging.exception(f"❌ Error inesperado procesando pregunta para {client_id}: {e}")
        return "Error: ocurrió un problema inesperado al procesar tu pregunta."
