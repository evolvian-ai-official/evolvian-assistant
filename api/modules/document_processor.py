import requests
from io import BytesIO
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from modules.chroma_indexer import save_to_chroma
import logging
import tempfile
import os

def process_file(file_url: str, client_id: str):
    try:
        logging.info(f"📥 Descargando archivo desde: {file_url}")
        response = requests.get(file_url)
        if response.status_code != 200:
            raise Exception(f"❌ No se pudo descargar el archivo desde Supabase. Código: {response.status_code}")

        content_type = response.headers.get("content-type", "")
        file_bytes = response.content

        # 🧠 Detectar si es PDF y cargarlo desde archivo temporal
        if ".pdf" in file_url.lower() or "pdf" in content_type.lower():
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name
            loader = PyPDFLoader(tmp_file_path)
        else:
            loader = TextLoader(file_path_or_file=BytesIO(file_bytes), encoding="utf-8")

        docs = loader.load()
        logging.info(f"📄 Documento cargado: {len(docs)} páginas/secciones")

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(docs)
        logging.info(f"🧠 Documento dividido en {len(chunks)} chunks")

        save_to_chroma(chunks, client_id)

        return chunks

    except Exception as e:
        logging.exception(f"❌ Error procesando el documento para {client_id}")
        raise e

    finally:
        # 🧹 Eliminar archivo temporal si fue creado
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"🗑️ Archivo temporal eliminado: {tmp_file_path}")
