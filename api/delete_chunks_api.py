# api/delete_chunks_api.py

from fastapi import APIRouter, Query, HTTPException
import shutil
from pathlib import Path

router = APIRouter()

@router.delete("/delete_chunks")
def delete_chunks(client_id: str = Query(...)):
    path = Path(f"chroma_db/{client_id}")

    if not path.exists():
        return {"deleted": False, "message": f"No existe ningún vectorstore para {client_id}"}

    try:
        shutil.rmtree(path)
        return {
            "deleted": True,
            "message": f"Vectores eliminados correctamente para {client_id}",
            "path": str(path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar vectorstore: {str(e)}")
