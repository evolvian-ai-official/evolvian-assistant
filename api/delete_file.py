# api/utils/delete_file.py

import logging
from urllib.parse import unquote

from api.config.config import supabase

BUCKET_NAME = "evolvian-documents"


def delete_file_from_storage(storage_path: str) -> None:
    """
    🔒 Helper interno (NO endpoint)

    Borra un archivo físico de Supabase Storage.
    - No toca metadata
    - No toca vectorstore
    - No toca contadores
    - No lanza HTTP errors
    """

    if not storage_path:
        logging.warning("⚠️ delete_file_from_storage called with empty storage_path")
        return

    clean_path = unquote(storage_path)

    logging.info(f"🗑️ Deleting file from storage: {clean_path}")

    try:
        res = supabase.storage.from_(BUCKET_NAME).remove([clean_path])

        if isinstance(res, dict) and res.get("error"):
            logging.error(
                f"❌ Storage deletion failed for {clean_path}: "
                f"{res['error'].get('message')}"
            )
        else:
            logging.info(f"✅ File removed from storage: {clean_path}")

    except Exception as e:
        # Best effort: nunca romper flujo RAG por storage
        logging.exception(
            f"❌ Unexpected error deleting file from storage: {clean_path}"
        )
