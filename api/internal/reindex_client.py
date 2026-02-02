# api/internal/reindex_single_client.py

import os
import shutil
import logging

from api.config.config import supabase
from api.modules.document_processor import process_file
from api.modules.storage_utils import get_signed_url

logging.basicConfig(level=logging.INFO)

def reindex_client(client_id: str):
    logging.info(f"🔄 Reindexing client {client_id}")

    chroma_path = os.path.abspath(f"./chroma_{client_id}")
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)

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
        logging.info(f"ℹ️ No documents for {client_id}")
        return

    for d in docs:
        signed_url = get_signed_url(d["storage_path"])
        process_file(file_url=signed_url, client_id=client_id)

    logging.info(f"✅ Finished reindex for {client_id}")
