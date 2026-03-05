# api/delete_chunks_api.py

from fastapi import APIRouter, Query, HTTPException, Request
from pathlib import Path
import shutil
import logging

from api.config.config import supabase
from api.delete_file import delete_file_from_storage  # helper interno
from api.authz import authorize_client_request
from api.utils.paths import get_base_data_path
from api.internal.reindex_single_client import reindex_client

router = APIRouter()


def _candidate_chroma_paths(client_id: str) -> list[Path]:
    """Compatibilidad: limpia la ruta actual y rutas legacy si existen."""
    base_path = Path(get_base_data_path())
    return [
        base_path / f"chroma_{client_id}",    # ruta vigente
        Path(f"./chroma_{client_id}"),        # ruta legacy
        Path("chroma_db") / client_id,        # ruta legacy antigua
    ]

@router.delete("/delete_chunks")
def delete_chunks(
    request: Request,
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
    authorize_client_request(request, client_id)

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
    removed_any = False
    for chroma_path in _candidate_chroma_paths(client_id):
        try:
            if chroma_path.exists():
                shutil.rmtree(chroma_path)
                removed_any = True
                logging.info(f"🗑️ Vectorstore cache removed: {chroma_path}")
        except Exception:
            # Cache invalidation should never block deletion
            logging.exception(
                "⚠️ Failed to remove vectorstore cache path %s for client %s",
                chroma_path,
                client_id,
            )
    if not removed_any:
        logging.info(f"ℹ️ No vectorstore cache found for client {client_id}")

    # --------------------------------------------------
    # 2.5️⃣ Rebuild vectorstore from active metadata
    # --------------------------------------------------
    reindex_status = "skipped"
    try:
        active_docs = (
            supabase
            .table("document_metadata")
            .select("id")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        ).data or []

        if active_docs:
            reindex_client(client_id)
            reindex_status = "reindexed"
        else:
            reindex_status = "no_active_docs"
    except Exception:
        logging.exception("⚠️ Reindex failed after deletion for client %s", client_id)
        reindex_status = "failed"

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
        "reindex_status": reindex_status,
    }
