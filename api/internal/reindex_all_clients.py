# api/internal/reindex_all_clients.py

import logging
from api.config.config import supabase
from api.internal.reindex_single_client import reindex_client

logging.basicConfig(level=logging.INFO)

def reindex_all_clients():
    logging.info("🚀 Starting GLOBAL reindex")

    response = (
        supabase
        .table("document_metadata")
        .select("client_id")
        .eq("is_active", True)
        .execute()
    )

    rows = response.data or []
    client_ids = sorted({row["client_id"] for row in rows})

    for client_id in client_ids:
        try:
            reindex_client(client_id)
        except Exception as e:
            logging.exception(f"❌ Failed reindex for {client_id}: {e}")

    logging.info("✅ GLOBAL reindex finished")

if __name__ == "__main__":
    reindex_all_clients()
