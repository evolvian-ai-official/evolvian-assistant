import os
import shutil
import logging

from api.config.config import supabase
from api.modules.document_processor import process_file
from api.modules.assistant_rag.supabase_client import get_signed_url

# --------------------------------------------------
# Configuración logging
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --------------------------------------------------
# Reindexar documentos de UN cliente
# --------------------------------------------------
def reindex_client(client_id: str):
    """
    Reindexa TODOS los documentos activos de un cliente.
    - Borra el índice Chroma anterior
    - Reprocesa documentos desde Supabase Storage
    - Genera vectores con la estructura nueva
    """

    logging.info(f"🔄 Starting reindex for client_id={client_id}")

    # --------------------------------------------------
    # 1️⃣ Limpiar índice Chroma viejo
    # --------------------------------------------------
    chroma_path = os.path.abspath(f"./chroma_{client_id}")

    if os.path.exists(chroma_path):
        logging.info(f"🧹 Removing old Chroma index at {chroma_path}")
        shutil.rmtree(chroma_path)
    else:
        logging.info("ℹ️ No existing Chroma index found (clean start)")

    # --------------------------------------------------
    # 2️⃣ Obtener documentos activos del cliente
    # --------------------------------------------------
    response = (
        supabase
        .table("documents")
        .select("storage_path")
        .eq("client_id", client_id)
        .execute()
    )

    docs = response.data if response else []

    if not docs:
        logging.info(f"ℹ️ No documents to reindex for client_id={client_id}")
        return

    logging.info(f"📄 {len(docs)} documents found for reindexing")

    # --------------------------------------------------
    # 3️⃣ Reprocesar cada documento
    # --------------------------------------------------
    total_chunks = 0

    for d in docs:
        storage_path = d.get("storage_path")
        if not storage_path:
            continue

        logging.info(f"📥 Reindexing document: {storage_path}")

        try:
            signed_url = get_signed_url(storage_path)

            chunks = process_file(
                file_url=signed_url,
                client_id=client_id
            )

            chunk_count = len(chunks) if chunks else 0
            total_chunks += chunk_count

            logging.info(
                f"🧩 Indexed {chunk_count} chunks "
                f"| client_id={client_id} "
                f"| document={storage_path}"
            )

        except Exception as e:
            logging.exception(
                f"❌ Failed to reindex document {storage_path} "
                f"for client_id={client_id}: {e}"
            )

    # --------------------------------------------------
    # 4️⃣ Final
    # --------------------------------------------------
    logging.info(
        f"✅ Reindex completed for client_id={client_id} "
        f"| total_chunks={total_chunks}"
    )


# --------------------------------------------------
# Runner manual (seguro para prod)
# --------------------------------------------------
if __name__ == "__main__":
    # ⚠️ Ejecuta SOLO un cliente primero
    TEST_CLIENT_ID = "2"

    reindex_client(TEST_CLIENT_ID)
