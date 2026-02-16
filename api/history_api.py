from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/history")
def get_history(
    request: Request,
    client_id: str = Query(...),
    session_id: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Devuelve el historial de un cliente.
    - Compatible con versión actual
    - Compatible con nuevas columnas (source_type, provider, status, etc.)
    - No rompe frontend existente
    """

    try:
        authorize_client_request(request, client_id)
        logger.info(f"📥 /history | client_id={client_id} | session_id={session_id}")

        # ✅ SELECT ampliado (si alguna columna no existe aún, Supabase la ignora)
        query = (
            supabase.table("history")
            .select("""
                role,
                content,
                created_at,
                session_id,
                channel,
                source_type,
                provider,
                status,
                source_id
            """)
            .eq("client_id", client_id)
        )

        if session_id:
            query = query.eq("session_id", session_id)

        response = query.order("created_at", desc=True).limit(limit).execute()

        raw_data = response.data or []
        logger.info(f"📦 Registros encontrados: {len(raw_data)}")

        # ---------------------------------------------------------
        # Limpieza defensiva (production safe)
        # ---------------------------------------------------------
        results = []
        for r in raw_data:
            if not isinstance(r, dict):
                continue
            if not r.get("content"):
                continue

            results.append({
                "role": r.get("role"),
                "content": r.get("content"),
                "created_at": r.get("created_at"),
                "session_id": r.get("session_id"),
                "channel": r.get("channel", "chat"),
                "source_type": r.get("source_type", "chat"),
                "provider": r.get("provider", "internal"),
                "status": r.get("status", "sent"),
                "source_id": r.get("source_id"),
            })

        if results:
            logger.info(
                f"🧩 Último mensaje: {results[0]['role']} - "
                f"{results[0]['content'][:60]}"
            )
        else:
            logger.info("ℹ️ No hay mensajes válidos para mostrar.")

        return JSONResponse(
            content={
                "client_id": client_id,
                "session_id": session_id,
                "count": len(results),
                "history": results,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error en /history")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
