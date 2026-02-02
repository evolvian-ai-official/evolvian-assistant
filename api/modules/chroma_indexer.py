# api/modules/chroma_indexer.py

import os
import logging
from typing import List, Optional
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
from api.utils.paths import get_base_data_path


# ✅ Factoría centralizada para crear un Chroma con OpenAI Embeddings
def get_chroma_vectorstore(
    chunks: List[Document],
    client_id: Optional[str] = None,
    persist: bool = True
) -> Chroma:
    """
    Crea un vectorstore Chroma usando OpenAIEmbeddings.
    
    Args:
        chunks (List[Document]): Lista de documentos ya divididos.
        client_id (Optional[str]): Si se pasa, se crea un directorio persistente aislado.
        persist (bool): Si True, guarda en disco. Si False, mantiene en memoria.

    Returns:
        Chroma: Vectorstore listo para usarse como retriever o para persistir.
    """
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

    persist_dir = None
    collection_name = "default"



    if client_id:
        base_path = get_base_data_path()
        persist_dir = os.path.join(base_path, f"chroma_{client_id}")
        os.makedirs(persist_dir, exist_ok=True)
        collection_name = client_id


    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,   # ✅ usa solo `embedding`
        persist_directory=persist_dir,
        collection_name=collection_name,  # ✅ usa la variable correcta
    )

    if persist and persist_dir:
        vectordb.persist()
        logging.info(f"💾 Persistencia activada para {client_id} en {persist_dir}")

    return vectordb


def save_to_chroma(chunks: List[Document], client_id: str):
    """
    Guarda chunks en un vectorstore Chroma persistente por cliente.
    """
    if not chunks:
        logging.warning(f"⚠️ No hay chunks para guardar en Chroma para {client_id}")
        return

    try:
        vectordb = get_chroma_vectorstore(chunks, client_id, persist=True)
        logging.info(f"✅ Chunks guardados exitosamente para {client_id}")
        return vectordb
    except Exception as e:
        logging.exception(f"❌ Error al guardar embeddings para {client_id}")
        raise e
