# api/upload_document.py

import os
import logging
import re
import unicodedata
import requests

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from api.config.config import supabase
from api.modules.document_processor import process_file
from api.utils.usage_limiter import check_and_increment_usage

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

logging.basicConfig(level=logging.INFO)


# --------------------------------------------------
# 🧼 Sanitizar nombre de archivo
# --------------------------------------------------
def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w.\-]", "_", name)
    return name.lower()


# --------------------------------------------------
# 📤 Upload + metadata + index
# --------------------------------------------------
@router.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...)
):
    try:
        # --------------------------------------------------
        # 1️⃣ Validar cliente + plan
        # --------------------------------------------------
        settings_res = (
            supabase
            .table("client_settings")
            .select("client_id, plan_id, plans(max_documents)")
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        settings = settings_res.data
        if not settings:
            raise HTTPException(status_code=404, detail="client_settings_not_found")

        max_documents = settings.get("plans", {}).get("max_documents") or 0

        # --------------------------------------------------
        # 2️⃣ Contar documentos activos (metadata)
        # --------------------------------------------------
        meta_res = (
            supabase
            .table("document_metadata")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
        )

        current_docs = meta_res.count or 0

        if max_documents and current_docs >= max_documents:
            raise HTTPException(status_code=403, detail="document_limit_reached")

        # --------------------------------------------------
        # 3️⃣ Subir archivo a Supabase Storage
        # --------------------------------------------------
        raw_content = await file.read()
        filename = sanitize_filename(file.filename)
        storage_path = f"{client_id}/{filename}"

        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        upload_url = (
            f"{supabase_url}/storage/v1/object/"
            f"{BUCKET_NAME}/{storage_path}?upsert=true"
        )

        headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": file.content_type or "application/octet-stream"
        }

        logging.info(f"📤 Uploading file → {storage_path}")

        res = requests.put(upload_url, headers=headers, data=raw_content)
        if res.status_code >= 400:
            logging.error(res.text)
            raise HTTPException(status_code=500, detail="storage_upload_failed")

        # --------------------------------------------------
        # 4️⃣ Guardar metadata (FUENTE DE VERDAD)
        # --------------------------------------------------
        supabase.table("document_metadata").insert({
            "client_id": client_id,
            "storage_path": storage_path,
            "file_name": filename,
            "mime_type": file.content_type,
            "is_active": True
        }).execute()

        # --------------------------------------------------
        # 5️⃣ Generar signed URL
        # --------------------------------------------------
        signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            storage_path,
            expires_in=3600
        )

        signed_url = signed.get("signedURL")
        if not signed_url:
            raise HTTPException(status_code=500, detail="signed_url_failed")

        # --------------------------------------------------
        # 6️⃣ Procesar documento (indexar)
        # --------------------------------------------------
        logging.info(f"🧠 Indexing document → {storage_path}")

        chunks = process_file(
            file_url=signed_url,
            client_id=client_id
        )

        # --------------------------------------------------
        # 7️⃣ Marcar como indexado
        # --------------------------------------------------
        supabase.table("document_metadata") \
            .update({"indexed_at": "now()"}) \
            .eq("storage_path", storage_path) \
            .execute()

        # --------------------------------------------------
        # 8️⃣ Actualizar uso
        # --------------------------------------------------
        check_and_increment_usage(
            client_id=client_id,
            usage_type="documents_uploaded",
            delta=1
        )

        return {
            "success": True,
            "message": "Document uploaded and indexed successfully",
            "file_name": filename,
            "storage_path": storage_path,
            "chunks": len(chunks)
        }

    except HTTPException:
        raise

    except Exception as e:
        logging.exception("❌ Unexpected error in /upload_document")
        raise HTTPException(status_code=500, detail=str(e))
