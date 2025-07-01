# api/list_chunks_api.py

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path

router = APIRouter()

@router.get("/list_chunks")
def list_chunks(client_id: str = Query(...)):
    try:
        base_path = Path(f"chroma_db/{client_id}")
        if not base_path.exists() or not base_path.is_dir():
            return {"exists": False, "message": f"No hay vectores guardados para {client_id}"}

        # Buscar archivos persistidos por Chroma
        files = list(base_path.glob("**/*"))
        file_list = [str(f.relative_to(base_path)) for f in files if f.is_file()]

        return {
            "exists": True,
            "client_id": client_id,
            "files": file_list,
            "total_files": len(file_list)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar chunks: {str(e)}")
