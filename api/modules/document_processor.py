import gc
import requests
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


def _guess_temp_suffix(file_url: str, content_type: str) -> str:
    content_type = (content_type or "").lower()
    if ".pdf" in (file_url or "").lower() or "pdf" in content_type:
        return ".pdf"
    if ".txt" in (file_url or "").lower() or "text/plain" in content_type:
        return ".txt"
    return ".bin"


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


def process_file(
    file_url: str,
    client_id: str,
    storage_path: str | None = None,
    return_chunks: bool = True,
):
    """
    Descarga un archivo desde Supabase, lo procesa, divide en chunks
    y lo guarda en Chroma de forma aislada por cliente.
    """
    response = None
    tmp_file_path = None
    docs = None
    chunks = None

    try:
        logging.info(f"📥 Descargando archivo desde: {file_url}")
        response = requests.get(file_url, stream=True, timeout=60)

        if response.status_code != 200:
            raise Exception(
                f"❌ No se pudo descargar el archivo desde Supabase. "
                f"Código: {response.status_code}"
            )

        content_type = response.headers.get("content-type", "")
        suffix = _guess_temp_suffix(file_url, content_type)

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp_file.write(chunk)
            tmp_file_path = tmp_file.name

        # --------------------------------------------------
        # 📄 Carga del documento
        # --------------------------------------------------
        if ".pdf" in file_url.lower() or "pdf" in content_type.lower():
            docs = load_pdf_with_fallback(tmp_file_path)
        else:
            loader = TextLoader(tmp_file_path, encoding="utf-8")
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

        if return_chunks:
            return chunks
        return None

    except Exception as e:
        logging.exception(f"❌ Error procesando el documento para {client_id}")
        raise e

    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                logging.warning("⚠️ Could not close streamed response cleanly")
        docs = None
        chunks = None
        gc.collect()
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"🗑️ Archivo temporal eliminado: {tmp_file_path}")
