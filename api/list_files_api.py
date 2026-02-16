# api/list_files_api.py

from fastapi import APIRouter, Query, HTTPException, Request
from api.config.config import supabase
from api.authz import authorize_client_request

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

@router.get("/list_files")
def list_files(request: Request, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)
        files = supabase.storage.from_(BUCKET_NAME).list(path=client_id)
        if not files:
            return {"files": []}

        result = []
        for file in files:
            storage_path = f"{client_id}/{file['name']}"
            signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(
                path=storage_path,
                expires_in=3600
            )
            result.append({
                "name": file["name"],  # solo el nombre
                "storage_path": storage_path,  # ruta completa
                "last_updated": file.get("updated_at"),
                "signed_url": signed.get("signedURL"),
                "size_kb": round(file.get("metadata", {}).get("size", 0) / 1024, 2)
            })

        return {"files": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")
