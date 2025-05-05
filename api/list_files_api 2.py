# api/list_files_api.py

from fastapi import APIRouter, Query, HTTPException
from config.config import supabase
import os

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

@router.get("/list_files")
def list_files(client_id: str = Query(...)):
    try:
        files = supabase.storage.from_(BUCKET_NAME).list(path=client_id)
        if not files:
            return {"files": []}

        # 🔐 Generar URL firmada por archivo
        result = []
        for file in files:
            signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(
                path=f"{client_id}/{file['name']}",
                expires_in=3600
            )
            result.append({
                "name": file["name"],
                "last_updated": file.get("updated_at"),
                "signed_url": signed.get("signedURL"),
                "size_kb": round(file.get("metadata", {}).get("size", 0) / 1024, 2)
            })

        return {"files": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")
