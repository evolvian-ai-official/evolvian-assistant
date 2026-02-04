# api/delete_chunks_api.py

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import shutil
import logging

from api.config.config import supabase
from api.delete_file import delete_file_from_storage  # helper interno

router = APIRouter()

@router.delete("/delete_chunks")
def delete_chunks(
    client_id: str = Query(..., description="Client ID owner of the document"),
    storage_path: str = Query(..., description="Full storage path of the document"),
):
    """
    🔥 Delete document (PROD SAFE)

    Contract:
    1) document_metadata is the SOURCE OF TRUTH
    2) Vectorstore (Chroma) is CACHE → fully invalidated
    3) Storage deletion is BEST-EFFORT (never breaks RAG)
    """

    # --------------------------------------------------
    # 1️⃣ Disable metadata (SOURCE OF TRUTH)
    # --------------------------------------------------
    res = (
        supabase
        .table("document_metadata")
        .update({"is_active": False})
        .eq("client_id", client_id)
        .eq("storage_path", storage_path)
        .execute()
    )

    if not res.data:
        raise HTTPException(
            status_code=404,
            detail="Document metadata not found or already inactive"
        )

    logging.info(
        f"🧹 Document disabled | client_id={client_id} | path={storage_path}"
    )

    # --------------------------------------------------
    # 2️⃣ Invalidate vectorstore (CACHE)
    # --------------------------------------------------
    chroma_path = Path(f"./chroma_{client_id}")

    try:
        if chroma_path.exists():
            shutil.rmtree(chroma_path)
            logging.info(f"🗑️ Vectorstore cache removed for client {client_id}")
        else:
            logging.info(f"ℹ️ No vectorstore cache found for client {client_id}")
    except Exception:
        # Cache invalidation should never block deletion
        logging.exception(
            f"⚠️ Failed to remove vectorstore cache for client {client_id}"
        )

    # --------------------------------------------------
    # 3️⃣ Delete file from storage (BEST EFFORT)
    # --------------------------------------------------
    try:
        delete_file_from_storage(storage_path)
    except Exception:
        # Never fail the request because of storage
        logging.exception(
            f"⚠️ Storage deletion failed (ignored) | path={storage_path}"
        )

    return {
        "success": True,
        "message": "Document deleted correctly",
        "client_id": client_id,
        "storage_path": storage_path,
    }
