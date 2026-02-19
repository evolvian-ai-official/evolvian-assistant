from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.authz import authorize_client_request
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()


class ClientEventPayload(BaseModel):
    client_id: str
    event_name: str = Field(min_length=2, max_length=120)
    event_category: Optional[str] = Field(default="interaction", max_length=80)
    event_label: Optional[str] = Field(default="", max_length=120)
    event_value: Optional[str] = Field(default="", max_length=120)
    event_key: Optional[str] = Field(default=None, max_length=180)
    metadata: Optional[dict[str, Any]] = None
    occurred_at: Optional[str] = None


@router.post("/client_event_log")
def log_client_event(payload: ClientEventPayload, request: Request):
    """
    Persist frontend analytics events in DB.
    Uses history as a durable event log (source_type=analytics_event)
    to avoid requiring a new table/migration.
    """
    try:
        authorize_client_request(request, payload.client_id)

        # Optional dedupe by event_key (idempotent events like step completion)
        if payload.event_key:
            existing = (
                supabase.table("history")
                .select("id")
                .eq("client_id", payload.client_id)
                .eq("source_type", "analytics_event")
                .eq("source_id", payload.event_key)
                .limit(1)
                .execute()
            )
            if existing.data:
                return {"success": True, "deduped": True}

        created_at = payload.occurred_at or datetime.utcnow().isoformat()

        event_metadata = {
            "event_name": payload.event_name,
            "event_category": payload.event_category or "interaction",
            "event_label": payload.event_label or "",
            "event_value": payload.event_value or "",
            "frontend_source": "clientuploader",
            "metadata": payload.metadata or {},
        }

        event_row = {
            "client_id": payload.client_id,
            "role": "assistant",
            "content": payload.event_name,
            "channel": "system",
            "source_type": "analytics_event",
            "provider": "internal",
            "status": "tracked",
            "source_id": payload.event_key,
            "metadata": event_metadata,
            "session_id": "__analytics__",
            "created_at": created_at,
        }

        res = supabase.table("history").insert(event_row).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to store analytics event")

        return {"success": True, "deduped": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging client event: {e}")
