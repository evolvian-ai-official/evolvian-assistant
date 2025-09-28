import os
import logging
import requests
import re
from typing import List
from tempfile import NamedTemporaryFile

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
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
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    return splitter.split_documents(documents)


def fetch_signed_documents(client_id: str) -> List[str]:
    """Obtiene URLs firmadas de Supabase (solo devuelve lista de URLs, sin imprimir tokens)."""
    try:
        res = list_documents_with_signed_urls(client_id)
        if not res:
            logging.info("📂 No hay documentos firmados disponibles.")
            return []
        urls = [doc["signed_url"] for doc in res if doc.get("signed_url")]

        # ⚠️ Evitar mostrar tokens firmados en logs
        filenames = [url.split("/")[-1].split("?")[0] for url in urls]
        logging.info(f"📂 Documentos firmados encontrados: {len(filenames)} → {filenames}")

        return urls
    except Exception as e:
        logging.error(f"❌ Error al obtener documentos firmados: {e}")
        return []


def ask_question(question: str, client_id: str, prompt: str = None) -> str:
    prompt = prompt or get_prompt_for_client(client_id)
    temperature = get_temperature_for_client(client_id)

    lower_question = question.strip().lower()
    if lower_question in ["hello", "hi", "hola"]:
        return "I'm your assistant. What can I do for you today?"

    # RAG pipeline
    signed_urls = fetch_signed_documents(client_id)
    logging.info(f"📄 Total documentos firmados: {len(signed_urls)}")

    if not signed_urls:
        return "No information found for this question."

    all_chunks = []
    used_docs = []

    for url in signed_urls:
        try:
            logging.info(f"📥 Descargando documento: {url.split('/')[-1].split('?')[0]}")  # solo nombre
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                logging.warning(f"❌ No se pudo descargar el documento (status {response.status_code})")
                continue

            suffix = ".pdf" if ".pdf" in url.lower() else ".txt"
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.content)
                tmp_file.flush()
                docs = load_document(tmp_file.name)
                chunks = chunk_documents(docs)

                source = url.split("/")[-1].split("?")[0]
                for chunk in chunks:
                    chunk.metadata["source"] = source

                used_docs.append(source)
                all_chunks.extend(chunks)

            logging.info(f"✂️ {source} particionado en {len(chunks)} chunks")

        except Exception as e:
            logging.warning(f"❌ Error procesando {url}: {e}")

    if not all_chunks:
        return "Error: no hay contenido disponible para generar una respuesta."

    logging.info("📚 Documentos utilizados para la respuesta:")
    for doc in used_docs:
        logging.info(f"   🔹 {doc}")

    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,  # ✅ FIX: parámetro correcto
        persist_directory=None,
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(temperature=temperature),
        retriever=vectordb.as_retriever(),
        return_source_documents=True,
        chain_type_kwargs={
            "prompt": PromptTemplate(
                template=f"{prompt}\n\nContexto:\n{{context}}\n\nPregunta:\n{{question}}",
                input_variables=["context", "question"],
            )
        },
    )

    try:
        result = qa_chain.invoke({"query": question})
        answer = result.get("result") or result.get("answer") or result.get("output_text") or ""
        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")

        try:
            save_history(client_id, question, answer)
        except Exception as e:
            logging.error(f"❌ Error al guardar historial: {e}")

        return answer

    except Exception as e:
        logging.exception(f"❌ Error inesperado procesando pregunta para {client_id}: {e}")
        return "Error: Ha ocurrido un problema inesperado al procesar tu pregunta."
