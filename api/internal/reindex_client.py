import logging
from api.config.config import supabase
from api.internal.reindex_client import reindex_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def reindex_all_clients():
    logging.info("🚀 Starting GLOBAL reindex (all clients)")

    response = (
        supabase
        .table("document_metadata")
        .select("client_id")
        .eq("is_active", True)
        .execute()
    )

    rows = response.data or []
    client_ids = sorted({row["client_id"] for row in rows})

    if not client_ids:
        logging.info("ℹ️ No clients with active documents")
        return

    logging.info(f"👥 Clients to reindex: {len(client_ids)}")

    for client_id in client_ids:
        try:
            logging.info(f"🔄 Reindexing client {client_id}")
            reindex_client(client_id)
        except Exception as e:
            logging.exception(f"❌ Failed reindex for {client_id}: {e}")

    logging.info("✅ GLOBAL reindex finished")


if __name__ == "__main__":
    reindex_all_clients()
