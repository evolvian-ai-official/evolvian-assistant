# test_rag_script.py

import os
from api.config import config

from api.modules.assistant_rag.rag_pipeline import (
    load_document,
    chunk_documents,
    embed_and_store,
    ask_question
)

# 👉 Define el ID del cliente
CLIENT_ID = "ev2"

# 👉 Ruta del archivo del cliente
FILE_PATH = f"data/{CLIENT_ID}/ejemplo.pdf"

# 1. Cargar el documento
print("📄 Cargando documento...")
docs = load_document(FILE_PATH)

# 2. Dividir en fragmentos
print("🔍 Dividiendo en fragmentos...")
chunks = chunk_documents(docs)

# 3. Embedding y almacenamiento
print(f"📦 Guardando vectores para cliente '{CLIENT_ID}'...")
embed_and_store(chunks, client_id=CLIENT_ID)

# 4. Preguntar a la IA
print("✅ Entrenamiento completo. Haz tus preguntas.\n")
while True:
    pregunta = input("🤖 Pregunta (o escribe 'salir'): ")
    if pregunta.lower() == "salir":
        break
    respuesta = ask_question(pregunta, client_id=CLIENT_ID)
    print(f"🧠 Respuesta: {respuesta}\n")
