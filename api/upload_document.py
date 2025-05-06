import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from io import BytesIO
import requests
import logging
import re
import unicodedata
from api.config.config import supabase
from api.modules.document_processor import process_file

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

# 🧼 Limpia nombres de archivo
def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    name = re.sub(r'[^\w.\-]', '_', name)
    return name

@router.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...)
):
    try:
        # 🔍 Obtener configuración del cliente + max_documents desde plans
        settings_response = supabase.table("client_settings") \
            .select("client_id, plan_id, plans(max_documents)") \
            .eq("client_id", client_id) \
            .single() \
            .execute()

        settings = settings_response.data

        if not settings:
            raise HTTPException(status_code=404, detail="client_settings_not_found")

        plan_id = settings.get("plan_id")
        max_documents = settings.get("plans", {}).get("max_documents", 1)

        # 📦 Contar archivos actuales en Supabase Storage para este cliente
        existing_files = supabase.storage.from_(BUCKET_NAME).list(path=client_id) or []
        file_count = len(existing_files)

        if file_count >= max_documents:
            raise HTTPException(
                status_code=403,
                detail="limit_reached"
            )

        # 📤 Subir archivo
        file_content = await file.read()
        filename = sanitize_filename(file.filename)
        storage_path = f"{client_id}/{filename}"

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        upload_url = f"{supabase_url}/storage/v1/object/{BUCKET_NAME}/{storage_path}?upsert=true"
        headers = {
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": file.content_type or "application/octet-stream"
        }

        logging.info("📤 Subiendo archivo a Supabase Storage...")
        logging.info(f"📦 Nombre de archivo: {filename}")
        logging.info(f"📁 Ruta en bucket: {storage_path}")
        logging.info(f"🔗 URL de carga: {upload_url}")

        upload_response = requests.put(
            upload_url,
            headers=headers,
            data=file_content
        )

        logging.info(f"📨 Respuesta del upload: {upload_response.status_code} - {upload_response.text}")

        if upload_response.status_code >= 400:
            raise HTTPException(
                status_code=upload_response.status_code,
                detail="upload_failed"
            )

        # 🔐 Generar URL firmada
        signed_url_response = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            path=storage_path,
            expires_in=3600
        )
        signed_url = signed_url_response.get("signedURL")
        if not signed_url:
            raise HTTPException(status_code=500, detail="signed_url_error")

        # 🧠 Procesar documento
        logging.info("🧠 Procesando documento...")
        chunks = process_file(file_url=signed_url, client_id=client_id)
        logging.info(f"✅ Documento procesado correctamente para {client_id}: {filename}")

        return {
            "message": "Documento subido y procesado correctamente",
            "chunks": len(chunks)
        }

    except HTTPException as e:
        raise e  # 🙌 No lo captures como error inesperado

    except Exception as e:
        logging.exception("❌ Error inesperado en /upload_document")
        raise HTTPException(status_code=500, detail=str(e))
