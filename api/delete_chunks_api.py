# api/delete_chunks_api.py

from fastapi import APIRouter, Query, HTTPException
import shutil
from pathlib import Path
from api.config.config import supabase
import logging

router = APIRouter()

@router.delete("/delete_chunks")
def delete_chunks(
    client_id: str = Query(...),
    storage_path: str = Query(...)
):
    """
    Elimina un documento de forma lógica:
    - Marca metadata como inactiva
    - Borra vectorstore local (cache)
    """

    # --------------------------------------------------
    # 1️⃣ Desactivar metadata (FUENTE DE VERDAD)
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
            detail="Document metadata not found"
        )

    logging.info(
        f"🧹 Document disabled | client_id={client_id} | path={storage_path}"
    )

    # --------------------------------------------------
    # 2️⃣ Borrar vectorstore (CACHE)
    # --------------------------------------------------
    chroma_path = Path(f"./chroma_{client_id}")

    if chroma_path.exists():
        shutil.rmtree(chroma_path)
        logging.info(f"🗑️ Vectorstore cache removed for {client_id}")

    return {
        "success": True,
        "message": "Document deleted correctly",
        "client_id": client_id,
        "storage_path": storage_path
    }
