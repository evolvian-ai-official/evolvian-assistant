import json
import logging
import sys
from pathlib import Path

from api.config.config import supabase
from api.utils.paths import get_base_data_path


logging.basicConfig(level=logging.INFO)


def _chroma_path(client_id: str) -> Path:
    return Path(get_base_data_path()) / f"chroma_{client_id}"


def _path_has_files(path: Path) -> bool:
    try:
        return path.exists() and any(path.iterdir())
    except Exception:
        logging.exception("⚠️ Could not inspect chroma path %s", path)
        return False


def audit_document_index_health() -> dict:
    rows = (
        supabase.table("document_metadata")
        .select("client_id, storage_path, indexed_at")
        .eq("is_active", True)
        .execute()
    ).data or []

    clients: dict[str, dict] = {}
    for row in rows:
        client_id = str(row.get("client_id") or "").strip()
        if not client_id:
            continue

        client_summary = clients.setdefault(
            client_id,
            {
                "client_id": client_id,
                "active_docs": 0,
                "missing_indexed_at": [],
            },
        )
        client_summary["active_docs"] += 1
        if not str(row.get("indexed_at") or "").strip():
            client_summary["missing_indexed_at"].append(
                str(row.get("storage_path") or "").strip() or "<missing_storage_path>"
            )

    at_risk_clients = []
    for client_summary in clients.values():
        chroma_path = _chroma_path(client_summary["client_id"])
        client_summary["chroma_path"] = str(chroma_path)
        client_summary["chroma_exists"] = chroma_path.exists()
        client_summary["chroma_has_files"] = _path_has_files(chroma_path)
        client_summary["risk_reasons"] = []

        if client_summary["active_docs"] > 0 and not client_summary["chroma_has_files"]:
            client_summary["risk_reasons"].append("missing_or_empty_chroma_index")
        if client_summary["missing_indexed_at"]:
            client_summary["risk_reasons"].append("missing_indexed_at")

        if client_summary["risk_reasons"]:
            at_risk_clients.append(client_summary)

    result = {
        "clients_total": len(clients),
        "clients_at_risk": len(at_risk_clients),
        "at_risk_clients": sorted(at_risk_clients, key=lambda row: row["client_id"]),
    }
    return result


if __name__ == "__main__":
    result = audit_document_index_health()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    sys.exit(1 if result["clients_at_risk"] else 0)
