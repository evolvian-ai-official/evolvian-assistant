# api/list_chunks_api.py

from fastapi import APIRouter, Query, HTTPException, Request
from pathlib import Path
import re
from api.authz import authorize_client_request
from api.utils.paths import get_base_data_path

router = APIRouter()
SAFE_CLIENT_ID = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")
CHROMA_ROOT = Path(get_base_data_path()).resolve()

@router.get("/list_chunks")
def list_chunks(request: Request, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)
        if not SAFE_CLIENT_ID.fullmatch(client_id):
            raise HTTPException(status_code=400, detail="Invalid client_id format")

        base_path = (CHROMA_ROOT / f"chroma_{client_id}").resolve()
        if CHROMA_ROOT not in base_path.parents:
            raise HTTPException(status_code=400, detail="Invalid client_id path")

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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar chunks: {str(e)}")
