from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
import logging
from typing import Any

router = APIRouter()
logger = logging.getLogger(__name__)


SYSTEM_SOURCE_TYPES = {
    "analytics_event",
    "compliance_outbound_policy",
}


def _is_system_history_event(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type") or "").strip().lower()
    if source_type in SYSTEM_SOURCE_TYPES:
        return True

    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        compliance_event = str(metadata.get("compliance_event") or "").strip().lower()
        if compliance_event == "outbound_policy":
            return True

    session_id = str(row.get("session_id") or "")
    content = str(row.get("content") or "").strip().lower()
    if session_id.startswith("proof_") and content.startswith("outbound policy "):
        return True

    return False


@router.get("/history")
def get_history(
    request: Request,
    client_id: str = Query(...),
    session_id: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    include_system_events: bool = Query(False),
):
    """
    Devuelve el historial de un cliente.
    - Compatible con versión actual
    - Compatible con nuevas columnas (source_type, provider, status, etc.)
    - No rompe frontend existente
    """

    try:
        authorize_client_request(request, client_id)
        logger.info(
            "📥 /history | client_id=%s | session_id=%s | include_system_events=%s",
            client_id,
            session_id,
            include_system_events,
        )

        # ✅ SELECT ampliado (si alguna columna no existe aún, Supabase la ignora)
        # Fetch extra rows when filtering system events so visible history still has enough items.
        raw_limit = limit if include_system_events else min(limit * 4, 800)
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
                source_id,
                metadata
            """)
            .eq("client_id", client_id)
        )

        if session_id:
            query = query.eq("session_id", session_id)

        response = query.order("created_at", desc=True).limit(raw_limit).execute()

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
            if not include_system_events and _is_system_history_event(r):
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
            if len(results) >= limit:
                break

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
