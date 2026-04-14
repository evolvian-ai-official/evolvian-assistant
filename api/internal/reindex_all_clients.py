# api/internal/reindex_all_clients.py

import logging
import sys
from api.config.config import supabase
from api.internal.reindex_single_client import reindex_client

logging.basicConfig(level=logging.INFO)

def reindex_all_clients():
    logging.info("🚀 Starting GLOBAL reindex")
    summary = {
        "clients_total": 0,
        "clients_ok": 0,
        "clients_with_failures": 0,
        "failed_clients": [],
        "results": [],
    }

    response = (
        supabase
        .table("document_metadata")
        .select("client_id")
        .eq("is_active", True)
        .execute()
    )

    rows = response.data or []
    client_ids = sorted({row["client_id"] for row in rows})
    summary["clients_total"] = len(client_ids)

    for client_id in client_ids:
        try:
            result = reindex_client(client_id)
            summary["results"].append(result)
            if result.get("status") == "partial_failure":
                summary["clients_with_failures"] += 1
                summary["failed_clients"].append(result)
                logging.error("❌ Reindex completed with failures for %s", client_id)
            else:
                summary["clients_ok"] += 1
        except Exception as e:
            logging.exception(f"❌ Failed reindex for {client_id}: {e}")
            summary["clients_with_failures"] += 1
            summary["failed_clients"].append(
                {
                    "client_id": client_id,
                    "status": "exception",
                    "error": str(e),
                }
            )

    logging.info("✅ GLOBAL reindex finished | %s", summary)
    return summary

if __name__ == "__main__":
    result = reindex_all_clients()
    sys.exit(1 if result["clients_with_failures"] else 0)
