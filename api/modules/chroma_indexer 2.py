from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from pathlib import Path
import os
import logging

def save_to_chroma(chunks, client_id: str):
    if not chunks:
        logging.warning(f"⚠️ No hay chunks para guardar en Chroma para {client_id}")
        return

    # 📁 Directorio donde se guardarán los vectores
    persist_directory = f"chroma_db/{client_id}"
    os.makedirs(persist_directory, exist_ok=True)

    try:
        # 🧠 Inicializa el modelo de embeddings (usa la OPENAI_API_KEY desde entorno)
        embedding_model = OpenAIEmbeddings()

        # 💾 Guarda los vectores
        vectordb = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            persist_directory=persist_directory
        )
        vectordb.persist()
        print(f"✅ Chunks guardados exitosamente para {client_id} en {persist_directory}")

    except Exception as e:
        logging.exception(f"❌ Error al guardar embeddings para {client_id}")
        raise e
