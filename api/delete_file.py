# api/delete_file.py

from fastapi import APIRouter, Query, HTTPException
import logging
from urllib.parse import unquote
from api.config.config import supabase
from api.utils.usage_limiter import check_and_increment_usage  # ✅

router = APIRouter()
BUCKET_NAME = "evolvian-documents"

@router.delete("/delete_file")
async def delete_file(
    storage_path: str = Query(..., description="Ruta completa del archivo en Storage")
):
    try:
        if not storage_path:
            raise HTTPException(status_code=400, detail="storage_path es requerido")

        # 🔑 Decode para convertir %2F -> /
        clean_path = unquote(storage_path)

        logging.info(f"🗑️ Eliminando archivo de Storage (raw): {storage_path}")
        logging.info(f"🗑️ Eliminando archivo de Storage (decoded): {clean_path}")

        # 🗑️ Eliminar archivo en Supabase Storage
        res = supabase.storage.from_(BUCKET_NAME).remove([clean_path])
        logging.info(f"📨 Respuesta Supabase Storage: {res}")

        if isinstance(res, dict) and res.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"storage_error: {res['error']['message']}"
            )

        # 🔹 Eliminar referencia en tabla documents
        try:
            supabase.table("documents").delete().match({
                "storage_path": clean_path
            }).execute()
            logging.info(f"🗑️ Registro eliminado en tabla documents para {clean_path}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo eliminar de documents: {e}")

        # ✅ Actualizar contador de documentos en client_usage
        client_id = clean_path.split("/")[0]  # El client_id es el primer segmento
        try:
            check_and_increment_usage(
                client_id=client_id,
                usage_type="documents_uploaded",
                delta=-1
            )
            logging.info(f"📉 Contador de documents_uploaded decrementado para {client_id}")
        except Exception as e:
            logging.error(f"⚠️ Error al decrementar documents_uploaded: {e}")

        return {
            "success": True,
            "message": "Archivo eliminado correctamente",
            "storage_path": clean_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error inesperado en /delete_file")
        raise HTTPException(status_code=500, detail=str(e))
