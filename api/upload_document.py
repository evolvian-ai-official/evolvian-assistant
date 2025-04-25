from fastapi import APIRouter, UploadFile, Form, Query, HTTPException
from fastapi.responses import JSONResponse
import os

import config.config
from utils.usage_limiter import check_and_increment_usage

from modules.assistant_rag.rag_pipeline import (
    load_document,
    chunk_documents,
    embed_and_store
)

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile, client_id: str = Form(...)):
    try:
        if not client_id or client_id.lower() == "undefined":
            raise HTTPException(status_code=400, detail="client_id no proporcionado o inválido")

        print(f"📥 client_id recibido en /upload: {client_id}")
        print(f"📄 Nombre de archivo recibido: {file.filename}")

        # Verificar límite de uso
        print("🔎 Verificando límites de documentos para el cliente...")
        check_and_increment_usage(client_id, usage_type="documents_uploaded")
        print("✅ Límite validado o cliente con plan ilimitado.")

        # Crear carpeta
        client_folder = f"data/{client_id}"
        os.makedirs(client_folder, exist_ok=True)
        print(f"📁 Carpeta asegurada: {client_folder}")

        # Guardar archivo
        file_path = os.path.join(client_folder, file.filename)
        with open(file_path, "wb") as f:
            file_data = await file.read()
            f.write(file_data)
        print(f"✅ Archivo guardado en: {file_path}")

        # Procesar con RAG
        print("🧠 Procesando documento con RAG...")
        docs = load_document(file_path)
        chunks = chunk_documents(docs)
        embed_and_store(chunks, client_id)
        print("✨ Documento embebido y almacenado correctamente.")

        return JSONResponse(content={"message": "Documento cargado y procesado correctamente."})

    except HTTPException as he:
        print(f"⚠️ HTTPException: {he.detail}")
        raise he
    except Exception as e:
        print(f"❌ Error inesperado en /upload: {type(e).__name__} - {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/list_files")
def list_files(client_id: str = Query(...)):
    try:
        if not client_id or client_id.lower() == "undefined":
            raise HTTPException(status_code=400, detail="client_id no proporcionado o inválido")

        folder_path = f"data/{client_id}"
        if not os.path.exists(folder_path):
            print(f"📂 Carpeta no existe para {client_id}")
            return JSONResponse(content={"files": []})
        
        files = os.listdir(folder_path)
        print(f"📑 Archivos listados: {files}")
        return JSONResponse(content={"files": files})

    except Exception as e:
        print(f"❌ Error listando archivos: {type(e).__name__} - {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
