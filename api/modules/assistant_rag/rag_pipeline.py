import os
import logging
import requests
import re
from typing import List
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from api.modules.calendar_logic import get_availability_from_google_calendar as get_calendar_availability
from api.modules.calendar_logic import save_appointment_if_valid  # esto lo creamos abajo
from api.modules.assistant_rag.supabase_client import supabase, save_history, list_documents_with_signed_urls

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."


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


def get_prompt_for_client(client_id: str) -> str:
    try:
        res = supabase.table("client_settings").select("custom_prompt").eq("client_id", client_id).single().execute()
        return res.data.get("custom_prompt") or DEFAULT_PROMPT
    except Exception as e:
        logging.warning(f"⚠️ No se pudo obtener el custom_prompt. Usando default. Error: {e}")
        return DEFAULT_PROMPT


def fetch_signed_documents(client_id: str) -> List[str]:
    try:
        res = list_documents_with_signed_urls(client_id)
        if not res:
            logging.info("📂 No hay documentos firmados disponibles.")
            return []
        urls = [doc["signed_url"] for doc in res if doc.get("signed_url")]
        logging.info(f"📂 Documentos firmados encontrados: {len(urls)}")
        return urls
    except Exception as e:
        logging.error(f"❌ Error al obtener documentos firmados: {e}")
        return []


def ask_question(question: str, client_id: str, prompt: str = None) -> str:
    prompt = prompt or get_prompt_for_client(client_id)

    # 🗓️ ¿El usuario intenta agendar una cita escribiendo un horario directamente?
    match = re.search(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?(?:-\d{2}:\d{2})?", question)
    if match:
        selected_time = match.group(0).replace(" ", "T")  # 🛠️ Normalizamos a ISO 8601
        message = save_appointment_if_valid(client_id, selected_time)
        return message

    # Aquí continúa tu lógica habitual de RAG...




    # 🧠 INTENCIÓN: consulta de disponibilidad de calendario
    if any(keyword in question.lower() for keyword in ["disponibilidad", "horario disponible", "agenda", "cita", "disponible", "calendar"]):
        try:
            calendar_data = get_calendar_availability(client_id=client_id)
            slots = calendar_data.get("available_slots", [])
            if not slots:
                return "No se encontraron horarios disponibles en los próximos 7 días."
            formatted = "\n".join(f"🕒 {slot.replace('T', ' ').split('.')[0]}" for slot in slots[:10])
            return f"Los próximos horarios disponibles son:\n{formatted}"
        except Exception as e:
            logging.error(f"❌ Error al consultar calendario: {e}")
            return "No fue posible consultar el calendario en este momento."
    
    # 🔍 Document retrieval continues here...
    signed_urls = fetch_signed_documents(client_id)
    logging.info(f"📄 Total documentos firmados: {len(signed_urls)}")

    if not signed_urls:
        logging.warning("⚠️ No se encontraron documentos para este asistente.")
        return "No documents found for this assistant."

    all_chunks = []
    used_docs = []

    for url in signed_urls:
        try:
            logging.info(f"📥 Descargando documento desde: {url}")
            response = requests.get(url)
            if response.status_code != 200:
                logging.warning(f"❌ No se pudo descargar el documento (status {response.status_code})")
                continue
            suffix = ".pdf" if ".pdf" in url else ".txt"
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.content)
                tmp_file.flush()
                docs = load_document(tmp_file.name)
                chunks = chunk_documents(docs)
                logging.info(f"✂️ Documento particionado en {len(chunks)} chunks")

                source = url.split("/")[-1].split("?")[0]
                for chunk in chunks:
                    chunk.metadata["source"] = source
                used_docs.append(source)

                all_chunks.extend(chunks)
        except Exception as e:
            logging.warning(f"❌ Error procesando {url}: {e}")

    logging.info(f"📦 Total chunks generados: {len(all_chunks)}")
    if not all_chunks:
        return "Error: no content to generate an answer."

    logging.info("📚 Documentos utilizados para la respuesta:")
    for doc in used_docs:
        logging.info(f"   🔹 {doc}")

    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=None
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(),
        retriever=vectordb.as_retriever(),
        return_source_documents=True,
        chain_type_kwargs={
            "prompt": PromptTemplate(
                template=f"{prompt}\n\nContexto:\n{{context}}\n\nPregunta:\n{{question}}",
                input_variables=["context", "question"]
            )
        }
    )

    try:
        result = qa_chain({"query": question})
        answer = result.get("result") or result.get("answer") or result.get("output_text") or ""
        logging.info(f"✅ Respuesta generada para {client_id}: {answer}")

        try:
            save_history(client_id, question, answer)
        except Exception as e:
            logging.error(f"❌ Error al guardar historial: {e}")

        return answer

    except Exception as e:
        logging.exception(f"❌ Error inesperado procesando pregunta para {client_id}: {e}")
        return "Error: An unexpected error occurred."