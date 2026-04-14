import gc
import logging
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import requests
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    PyPDFium2Loader
)
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from api.modules.chroma_indexer import save_to_chroma


MAX_PDF_PAGES = int(os.getenv("EVOLVIAN_MAX_PDF_PAGES") or "400")
MAX_DOCUMENT_CHARS = int(os.getenv("EVOLVIAN_MAX_DOCUMENT_CHARS") or "1200000")
MAX_DOCUMENT_CHUNKS = int(os.getenv("EVOLVIAN_MAX_DOCUMENT_CHUNKS") or "2000")


class DocumentProcessingError(Exception):
    """Base class for document ingestion failures."""


class DocumentExtractionError(DocumentProcessingError):
    """Raised when no text can be extracted from a document."""


class DocumentTooLargeError(DocumentProcessingError):
    """Raised when a document exceeds safe ingestion limits."""


def _guess_temp_suffix(file_url: str, content_type: str) -> str:
    content_type = (content_type or "").lower()
    if ".pdf" in (file_url or "").lower() or "pdf" in content_type:
        return ".pdf"
    if ".docx" in (file_url or "").lower() or "wordprocessingml.document" in content_type:
        return ".docx"
    if ".txt" in (file_url or "").lower() or "text/plain" in content_type:
        return ".txt"
    return ".bin"


def load_pdf_with_fallback(file_path: str):
    """
    Intenta cargar un PDF con diferentes loaders hasta encontrar texto válido.
    Evita PDFs escaneados o vacíos.
    """
    try:
        page_count = len(PdfReader(file_path).pages)
        if MAX_PDF_PAGES > 0 and page_count > MAX_PDF_PAGES:
            raise DocumentTooLargeError(
                f"❌ El documento excede el límite seguro de páginas ({page_count} > {MAX_PDF_PAGES})."
            )
    except DocumentTooLargeError:
        raise
    except Exception as error:
        logging.warning("⚠️ No se pudo inspeccionar el PDF antes de cargarlo: %s", error)

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

    raise DocumentExtractionError("❌ No se pudo extraer texto del PDF con ningún loader")


def load_docx_with_fallback(file_path: str):
    """
    Extrae texto de un Word moderno (.docx) sin dependencias externas.
    """
    try:
        with zipfile.ZipFile(file_path) as archive:
            raw_xml = archive.read("word/document.xml")
    except KeyError as error:
        raise DocumentExtractionError("❌ El archivo Word no contiene texto legible.") from error
    except zipfile.BadZipFile as error:
        raise DocumentExtractionError("❌ El archivo Word está dañado o no es un .docx válido.") from error

    root = ET.fromstring(raw_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []

    for paragraph in root.findall(".//w:p", namespace):
        runs = [
            node.text.strip()
            for node in paragraph.findall(".//w:t", namespace)
            if node.text and node.text.strip()
        ]
        if runs:
            paragraphs.append(" ".join(runs))

    text = "\n".join(paragraphs).strip()
    if not text:
        raise DocumentExtractionError("❌ No se pudo extraer texto del Word con ningún loader")

    logging.info(
        "🔍 Loader DOCX -> %s párrafos, %s caracteres extraídos",
        len(paragraphs),
        len(text),
    )
    return [Document(page_content=text, metadata={"source": file_path})]


def _summarize_docs(docs) -> tuple[int, int]:
    page_count = len(docs or [])
    total_chars = sum(len((doc.page_content or "").strip()) for doc in (docs or []))
    return page_count, total_chars


def _enforce_document_limits(docs) -> None:
    page_count, total_chars = _summarize_docs(docs)

    if MAX_PDF_PAGES > 0 and page_count > MAX_PDF_PAGES:
        raise DocumentTooLargeError(
            f"❌ El documento excede el límite seguro de páginas ({page_count} > {MAX_PDF_PAGES})."
        )

    if MAX_DOCUMENT_CHARS > 0 and total_chars > MAX_DOCUMENT_CHARS:
        raise DocumentTooLargeError(
            f"❌ El documento excede el límite seguro de texto extraído ({total_chars} > {MAX_DOCUMENT_CHARS})."
        )


def _enforce_chunk_limit(chunks) -> None:
    chunk_count = len(chunks or [])
    if MAX_DOCUMENT_CHUNKS > 0 and chunk_count > MAX_DOCUMENT_CHUNKS:
        raise DocumentTooLargeError(
            f"❌ El documento genera demasiados chunks para indexar de forma segura ({chunk_count} > {MAX_DOCUMENT_CHUNKS})."
        )


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
        elif ".docx" in file_url.lower() or "wordprocessingml.document" in content_type.lower():
            docs = load_docx_with_fallback(tmp_file_path)
        else:
            loader = TextLoader(tmp_file_path, encoding="utf-8")
            docs = loader.load()

        logging.info(f"📄 Documento cargado: {len(docs)} páginas/secciones")
        _enforce_document_limits(docs)

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
        _enforce_chunk_limit(chunks)

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
