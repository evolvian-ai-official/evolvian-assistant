# api/internal/reindex_single_client.py

import os
import shutil
import logging

from api.config.config import supabase
from api.modules.document_processor import process_file
from api.modules.storage_utils import get_signed_url
from api.utils.paths import get_base_data_path


logging.basicConfig(level=logging.INFO)

def reindex_client(client_id: str):
    logging.info(f"🔄 Reindexing client {client_id}")

    # =====================================================
    # 📂 Path ÚNICO y consistente para Chroma
    # =====================================================
    base_path = get_base_data_path()
    chroma_path = os.path.join(base_path, f"chroma_{client_id}")

    logging.info(f"📂 Using chroma path: {chroma_path}")

    # 🔥 Borrar índice previo si existe
    if os.path.exists(chroma_path):
        logging.info("🧹 Removing existing vectorstore")
        shutil.rmtree(chroma_path)

    # =====================================================
    # 📄 Obtener documentos activos del cliente
    # =====================================================
    response = (
        supabase
        .table("document_metadata")
        .select("storage_path")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )

    docs = response.data or []
    if not docs:
        logging.info(f"ℹ️ No active documents for client {client_id}")
        return

    # =====================================================
    # 🧠 Vectorizar documentos
    # =====================================================
    for d in docs:
        try:
            signed_url = get_signed_url(d["storage_path"])
            logging.info(f"📄 Processing document: {d['storage_path']}")
            process_file(
                file_url=signed_url,
                client_id=client_id,
                storage_path=d["storage_path"],
            )
        except Exception as e:
            logging.exception(f"❌ Failed processing {d['storage_path']}: {e}")

    logging.info(f"✅ Finished reindex for client {client_id}")
