# api/upload_document.py

import os
import logging
from pathlib import Path
import re
import unicodedata
import requests

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request

from api.config.config import supabase
from api.authz import authorize_client_request
from api.delete_file import delete_file_from_storage
from api.modules.document_processor import (
    DocumentExtractionError,
    DocumentTooLargeError,
    process_file,
)
from api.internal.reindex_single_client import reindex_client
from api.utils.effective_plan import normalize_plan_id, resolve_effective_plan_id
from api.utils.usage_limiter import check_and_increment_usage

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

logging.basicConfig(level=logging.INFO)
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".docx"}
PDF_MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024


# --------------------------------------------------
# 🧼 Sanitizar nombre de archivo
# --------------------------------------------------
def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w.\-]", "_", name)
    return name.lower()


def _validate_upload_candidate(filename: str, content_type: str, size_bytes: int) -> None:
    extension = Path(filename or "").suffix.lower()
    normalized_content_type = (content_type or "").lower()

    if normalized_content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="image_uploads_not_allowed")

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported_document_type")

    if extension == ".pdf" and size_bytes > PDF_MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="pdf_file_too_large")


def _mark_document_inactive(client_id: str, storage_path: str) -> None:
    if not client_id or not storage_path:
        return

    (
        supabase.table("document_metadata")
        .update({"is_active": False})
        .eq("client_id", client_id)
        .eq("storage_path", storage_path)
        .eq("is_active", True)
        .execute()
    )


def _deactivate_document_ids(document_ids: list[str]) -> None:
    for document_id in document_ids:
        (
            supabase.table("document_metadata")
            .update({"is_active": False})
            .eq("id", document_id)
            .execute()
        )


def _activate_document(document_id: str | None, storage_path: str) -> None:
    query = supabase.table("document_metadata").update(
        {"is_active": True, "indexed_at": "now()"}
    )

    if document_id:
        query = query.eq("id", document_id)
    else:
        query = query.eq("storage_path", storage_path).eq("is_active", False)

    query.execute()


# --------------------------------------------------
# 📤 Upload + metadata + index
# --------------------------------------------------
@router.post("/upload_document")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    client_id: str = Form(...)
):
    storage_path = ""
    new_document_id = None
    try:
        authorize_client_request(request, client_id)
        # --------------------------------------------------
        # 1️⃣ Validar cliente + plan
        # --------------------------------------------------
        settings_res = (
            supabase
            .table("client_settings")
            .select("client_id, plan_id, plans(id, max_documents, is_unlimited)")
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        settings = settings_res.data
        if not settings:
            raise HTTPException(status_code=404, detail="client_settings_not_found")

        base_plan_id = normalize_plan_id(settings.get("plan_id"))
        effective_plan_id = resolve_effective_plan_id(
            client_id,
            base_plan_id=base_plan_id,
            supabase_client=supabase,
        )

        plan_limits = settings.get("plans", {}) or {}
        if effective_plan_id != base_plan_id:
            override_plan_res = (
                supabase.table("plans")
                .select("id, max_documents, is_unlimited")
                .eq("id", effective_plan_id)
                .maybe_single()
                .execute()
            )
            if override_plan_res and override_plan_res.data:
                plan_limits = override_plan_res.data

        max_documents = plan_limits.get("max_documents") or 0
        is_unlimited = bool(plan_limits.get("is_unlimited"))

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

        if not is_unlimited and max_documents and current_docs >= max_documents:
            raise HTTPException(status_code=403, detail="document_limit_reached")

        # --------------------------------------------------
        # 3️⃣ Subir archivo a Supabase Storage
        # --------------------------------------------------
        raw_content = await file.read()
        _validate_upload_candidate(file.filename, file.content_type, len(raw_content))
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
        #     Si el path ya existía activo, se desactiva la versión previa.
        # --------------------------------------------------
        existing_same_path = (
            supabase
            .table("document_metadata")
            .select("id")
            .eq("client_id", client_id)
            .eq("storage_path", storage_path)
            .eq("is_active", True)
            .execute()
        ).data or []

        had_prior_active_path = bool(existing_same_path)
        insert_result = supabase.table("document_metadata").insert({
            "client_id": client_id,
            "storage_path": storage_path,
            "file_name": filename,
            "mime_type": file.content_type,
            "is_active": False
        }).execute()
        inserted_rows = insert_result.data or []
        if inserted_rows:
            new_document_id = inserted_rows[0].get("id")

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
            client_id=client_id,
            storage_path=storage_path,
        )

        # --------------------------------------------------
        # 7️⃣ Marcar como indexado
        # --------------------------------------------------
        _activate_document(new_document_id, storage_path)

        # Si hubo reemplazo de versión en el mismo path, reconstruimos índice.
        if had_prior_active_path:
            _deactivate_document_ids([
                str(row.get("id"))
                for row in existing_same_path
                if row.get("id")
            ])
            logging.info(
                "♻️ Existing active file replaced; rebuilding vectorstore for client %s",
                client_id,
            )
            reindex_client(client_id)

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

    except DocumentTooLargeError as error:
        logging.warning("⚠️ Upload rejected for oversized document: %s", storage_path)
        _mark_document_inactive(client_id, storage_path)
        delete_file_from_storage(storage_path)
        raise HTTPException(status_code=413, detail=str(error))

    except DocumentExtractionError as error:
        logging.warning("⚠️ Upload rejected for unreadable document: %s", storage_path)
        _mark_document_inactive(client_id, storage_path)
        delete_file_from_storage(storage_path)
        raise HTTPException(status_code=422, detail=str(error))

    except Exception as e:
        logging.exception("❌ Unexpected error in /upload_document")
        raise HTTPException(status_code=500, detail=str(e))
