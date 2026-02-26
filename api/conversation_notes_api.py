from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from api.authz import authorize_client_request
from api.modules.assistant_rag.supabase_client import supabase
from api.utils.feature_access import require_client_feature


router = APIRouter()
logger = logging.getLogger(__name__)


class ConversationInternalNoteCreateInput(BaseModel):
    client_id: str
    conversation_id: str
    handoff_request_id: Optional[str] = None
    note: str


@router.get("/conversation_internal_notes")
def list_conversation_internal_notes(
    request: Request,
    client_id: str = Query(...),
    conversation_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        authorize_client_request(request, client_id)
        require_client_feature(client_id, "handoff", required_plan_label="premium")

        res = (
            supabase.table("conversation_internal_notes")
            .select("id,client_id,conversation_id,handoff_request_id,author_user_id,note,created_at")
            .eq("client_id", client_id)
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"items": res.data or []}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing conversation internal notes")
        raise HTTPException(status_code=500, detail=f"Conversation notes error: {e}")


@router.post("/conversation_internal_notes")
def create_conversation_internal_note(payload: ConversationInternalNoteCreateInput, request: Request):
    try:
        auth_user_id = authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")
        note_text = str(payload.note or "").strip()
        if not note_text:
            raise HTTPException(status_code=422, detail="note is required")

        row = {
            "client_id": payload.client_id,
            "conversation_id": payload.conversation_id,
            "handoff_request_id": payload.handoff_request_id,
            "author_user_id": auth_user_id,
            "note": note_text[:4000],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        res = supabase.table("conversation_internal_notes").insert(row).execute()
        if not res or not res.data:
            raise HTTPException(status_code=500, detail="Failed to create note")
        return {"success": True, "item": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating conversation internal note")
        raise HTTPException(status_code=500, detail=f"Conversation notes create error: {e}")
