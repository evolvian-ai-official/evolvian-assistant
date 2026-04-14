# api/internal/reindex_single_client.py

import logging
import shutil
import gc
from datetime import datetime, timezone
from pathlib import Path

from api.config.config import supabase
from api.modules.document_processor import process_file
from api.modules.storage_utils import get_signed_url
from api.utils.paths import get_base_data_path


logging.basicConfig(level=logging.INFO)


def _candidate_chroma_paths(client_id: str) -> list[Path]:
    """Compatibilidad con rutas vigentes y legacy del vectorstore."""
    base_path = Path(get_base_data_path())
    return [
        base_path / f"chroma_{client_id}",
        Path(f"./chroma_{client_id}"),
        Path("chroma_db") / client_id,
    ]


def _mark_document_indexed(client_id: str, storage_path: str) -> None:
    supabase.table("document_metadata").update(
        {"indexed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("client_id", client_id).eq("storage_path", storage_path).eq(
        "is_active", True
    ).execute()


def reindex_client(client_id: str) -> dict:
    logging.info("🔄 Reindexing client %s", client_id)

    primary_chroma_path = str(Path(get_base_data_path()) / f"chroma_{client_id}")
    summary = {
        "client_id": client_id,
        "status": "success",
        "docs_total": 0,
        "docs_reindexed": 0,
        "docs_failed": 0,
        "failed_paths": [],
        "cleared_paths": [],
        "chroma_path": primary_chroma_path,
    }

    for chroma_path in _candidate_chroma_paths(client_id):
        try:
            if chroma_path.exists():
                logging.info("🧹 Removing existing vectorstore: %s", chroma_path)
                shutil.rmtree(chroma_path)
                summary["cleared_paths"].append(str(chroma_path))
        except Exception:
            logging.exception(
                "⚠️ Failed removing vectorstore path %s for client %s",
                chroma_path,
                client_id,
            )

    response = (
        supabase.table("document_metadata")
        .select("storage_path")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )

    docs = response.data or []
    summary["docs_total"] = len(docs)
    if not docs:
        summary["status"] = "no_active_docs"
        logging.info("ℹ️ No active documents for client %s", client_id)
        return summary

    for doc in docs:
        storage_path = str(doc.get("storage_path") or "").strip()
        if not storage_path:
            summary["docs_failed"] += 1
            summary["failed_paths"].append("<missing_storage_path>")
            logging.error("❌ Active document without storage_path for client %s", client_id)
            continue

        try:
            signed_url = get_signed_url(storage_path)
            logging.info("📄 Processing document: %s", storage_path)
            process_file(
                file_url=signed_url,
                client_id=client_id,
                storage_path=storage_path,
                return_chunks=False,
            )
            _mark_document_indexed(client_id, storage_path)
            summary["docs_reindexed"] += 1
        except Exception:
            summary["docs_failed"] += 1
            summary["failed_paths"].append(storage_path)
            logging.exception("❌ Failed processing %s", storage_path)
        finally:
            gc.collect()

    if summary["docs_failed"] > 0:
        summary["status"] = "partial_failure"

    logging.info("✅ Finished reindex for client %s | %s", client_id, summary)
    return summary
