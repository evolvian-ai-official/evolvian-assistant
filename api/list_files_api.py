# api/list_files_api.py

import logging

from fastapi import APIRouter, Query, HTTPException, Request

from api.config.config import supabase
from api.authz import authorize_client_request

router = APIRouter()
BUCKET_NAME = "evolvian-documents"


def _extract_signed_url(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("signedURL") or payload.get("signed_url")


@router.get("/list_files")
def list_files(request: Request, client_id: str = Query(...)):
    try:
        authorize_client_request(request, client_id)

        # Source of truth: active documents in metadata.
        metadata_rows = (
            supabase.table("document_metadata")
            .select("storage_path, file_name, indexed_at")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
        ).data or []

        if not metadata_rows:
            return {"files": []}

        # Best-effort enrichment with Storage size/updated_at.
        storage_size_by_path: dict[str, float] = {}
        storage_updated_by_path: dict[str, str | None] = {}
        try:
            storage_rows = supabase.storage.from_(BUCKET_NAME).list(path=client_id) or []
            for row in storage_rows:
                name = row.get("name")
                if not name:
                    continue
                path = f"{client_id}/{name}"
                size_raw = (row.get("metadata") or {}).get("size") or 0
                try:
                    size_kb = round(float(size_raw) / 1024, 2)
                except (TypeError, ValueError):
                    size_kb = 0.0
                storage_size_by_path[path] = size_kb
                storage_updated_by_path[path] = row.get("updated_at")
        except Exception:
            logging.exception("⚠️ Storage listing failed in /list_files (non-blocking)")

        # Deduplicate by storage_path to avoid duplicated rows after re-uploads.
        seen_paths: set[str] = set()
        result = []
        for row in metadata_rows:
            storage_path = (row.get("storage_path") or "").strip()
            if not storage_path or storage_path in seen_paths:
                continue
            seen_paths.add(storage_path)

            file_name = (row.get("file_name") or storage_path.rsplit("/", 1)[-1]).strip()

            signed_url = None
            try:
                signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(storage_path, 3600)
                signed_url = _extract_signed_url(signed)
            except Exception:
                logging.warning(
                    "⚠️ Could not create signed URL for %s (non-blocking)",
                    storage_path,
                )

            result.append(
                {
                    "name": file_name,
                    "storage_path": storage_path,
                    "last_updated": storage_updated_by_path.get(storage_path) or row.get("indexed_at"),
                    "signed_url": signed_url,
                    "size_kb": storage_size_by_path.get(storage_path, 0.0),
                }
            )

        result.sort(key=lambda item: str(item.get("name") or "").lower())
        return {"files": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")
