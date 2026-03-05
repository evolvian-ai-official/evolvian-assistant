import requests
from io import BytesIO
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    PyPDFium2Loader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from api.modules.chroma_indexer import save_to_chroma
import logging
import tempfile
import os


def load_pdf_with_fallback(file_path: str):
    """
    Intenta cargar un PDF con diferentes loaders hasta encontrar texto válido.
    Evita PDFs escaneados o vacíos.
    """
    loaders = [
        ("PyPDFLoader", PyPDFLoader(file_path)),
        ("PyPDFium2Loader", PyPDFium2Loader(file_path)),
    ]

    for name, loader in loaders:
        try:
            docs = loader.load()
            total_text = sum(len(doc.page_content.strip()) for doc in docs)

            logging.info(
                f"🔍 Loader {name} -> {len(docs)} páginas, "
                f"{total_text} caracteres extraídos"
            )

            if total_text > 0:
                logging.info(f"✅ Usando {name} para este PDF")
                return docs

        except Exception as e:
            logging.warning(f"⚠️ Error con {name}: {e}")

    raise Exception("❌ No se pudo extraer texto del PDF con ningún loader")


def process_file(file_url: str, client_id: str, storage_path: str | None = None):
    """
    Descarga un archivo desde Supabase, lo procesa, divide en chunks
    y lo guarda en Chroma de forma aislada por cliente.
    """
    tmp_file_path = None

    try:
        logging.info(f"📥 Descargando archivo desde: {file_url}")
        response = requests.get(file_url)

        if response.status_code != 200:
            raise Exception(
                f"❌ No se pudo descargar el archivo desde Supabase. "
                f"Código: {response.status_code}"
            )

        content_type = response.headers.get("content-type", "")
        file_bytes = response.content

        # --------------------------------------------------
        # 📄 Carga del documento
        # --------------------------------------------------
        if ".pdf" in file_url.lower() or "pdf" in content_type.lower():
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name

            docs = load_pdf_with_fallback(tmp_file_path)
        else:
            loader = TextLoader(
                file_path_or_file=BytesIO(file_bytes),
                encoding="utf-8"
            )
            docs = loader.load()

        logging.info(f"📄 Documento cargado: {len(docs)} páginas/secciones")

        for i, doc in enumerate(docs[:5]):
            logging.info(
                f"Página {i + 1} -> {len(doc.page_content.strip())} caracteres"
            )

        # --------------------------------------------------
        # ✂️ Chunking
        # --------------------------------------------------
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )

        chunks = splitter.split_documents(docs)
        logging.info(f"🧠 Documento dividido en {len(chunks)} chunks")

        # --------------------------------------------------
        # 🔐 Blindaje multi-tenant + trazabilidad por archivo
        # --------------------------------------------------
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["client_id"] = client_id
            if storage_path:
                chunk.metadata["storage_path"] = storage_path
                # Normalizamos "source" para facilitar depuración y filtros.
                chunk.metadata["source"] = storage_path

        # --------------------------------------------------
        # 💾 Guardar en Chroma (indexer intacto)
        # --------------------------------------------------
        save_to_chroma(chunks, client_id)

        return chunks

    except Exception as e:
        logging.exception(f"❌ Error procesando el documento para {client_id}")
        raise e

    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"🗑️ Archivo temporal eliminado: {tmp_file_path}")
