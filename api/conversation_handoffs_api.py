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

HANDOFF_STATUSES = {"open", "assigned", "in_progress", "resolved", "dismissed"}


class ConversationHandoffUpdateInput(BaseModel):
    client_id: str
    status: Optional[str] = None
    assign_to_me: bool = False
    clear_assignee: bool = False
    assigned_user_id: Optional[str] = None
    internal_resolution_note: Optional[str] = None


def _get_allowed_assignee_ids(client_id: str, auth_user_id: str) -> set[str]:
    allowed = {str(auth_user_id)}
    try:
        client_res = (
            supabase.table("clients")
            .select("user_id")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        owner_id = str((client_res.data or {}).get("user_id") or "").strip()
        if owner_id:
            allowed.add(owner_id)
    except Exception as e:
        logger.warning("Could not resolve owner assignee for client %s: %s", client_id, e)
    return {v for v in allowed if v}


@router.get("/conversation_assignees")
def list_conversation_assignees(
    request: Request,
    client_id: str = Query(...),
):
    try:
        auth_user_id = authorize_client_request(request, client_id)
        require_client_feature(client_id, "handoff", required_plan_label="premium")
        allowed_ids = list(_get_allowed_assignee_ids(client_id, auth_user_id))
        if not allowed_ids:
            return {"items": []}

        users_res = (
            supabase.table("users")
            .select("id,email")
            .in_("id", allowed_ids)
            .execute()
        )
        users = users_res.data or []
        by_id = {str(u.get("id")): u for u in users if u.get("id")}

        items = []
        for uid in allowed_ids:
            row = by_id.get(uid, {"id": uid, "email": None})
            items.append(
                {
                    "id": uid,
                    "email": row.get("email"),
                    "is_current_user": uid == auth_user_id,
                }
            )

        items.sort(key=lambda x: (not x.get("is_current_user"), str(x.get("email") or x.get("id"))))
        return {"items": items}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing conversation assignees")
        raise HTTPException(status_code=500, detail=f"Conversation assignees error: {e}")


@router.patch("/conversation_handoff_requests/{handoff_id}")
def update_conversation_handoff_request(
    handoff_id: str,
    payload: ConversationHandoffUpdateInput,
    request: Request,
):
    try:
        auth_user_id = authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")
        allowed_assignees = _get_allowed_assignee_ids(payload.client_id, auth_user_id)

        existing_res = (
            supabase.table("conversation_handoff_requests")
            .select("id,client_id,status,assigned_user_id,conversation_id")
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .maybe_single()
            .execute()
        )
        existing = existing_res.data if existing_res else None
        if not existing:
            raise HTTPException(status_code=404, detail="Handoff request not found")

        update_payload = {"updated_at": datetime.now(timezone.utc).isoformat()}
        next_status = None
        if payload.status is not None:
            next_status = str(payload.status).strip().lower()
            if next_status not in HANDOFF_STATUSES:
                raise HTTPException(status_code=400, detail="Invalid handoff status")
            update_payload["status"] = next_status
            if next_status in {"resolved", "dismissed"}:
                update_payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
            else:
                update_payload["resolved_at"] = None

        if payload.assign_to_me:
            update_payload["assigned_user_id"] = auth_user_id
            if "status" not in update_payload and str(existing.get("status") or "").lower() == "open":
                update_payload["status"] = "assigned"
                next_status = "assigned"
        elif payload.clear_assignee:
            update_payload["assigned_user_id"] = None
        elif payload.assigned_user_id is not None:
            explicit_assignee = str(payload.assigned_user_id or "").strip()
            if not explicit_assignee:
                update_payload["assigned_user_id"] = None
            else:
                if explicit_assignee not in allowed_assignees:
                    raise HTTPException(status_code=403, detail="Invalid assignee for this client")
                update_payload["assigned_user_id"] = explicit_assignee
                if "status" not in update_payload and str(existing.get("status") or "").lower() == "open":
                    update_payload["status"] = "assigned"
                    next_status = "assigned"

        if payload.internal_resolution_note is not None:
            note_text = str(payload.internal_resolution_note or "").strip()
            update_payload["internal_resolution_note"] = note_text[:4000] or None

        if len(update_payload) == 1:  # only updated_at
            raise HTTPException(status_code=400, detail="No valid handoff updates provided")

        updated_res = (
            supabase.table("conversation_handoff_requests")
            .update(update_payload)
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        updated_item = (updated_res.data or [{}])[0]

        # Best-effort sync: reflect handoff lifecycle in conversation alerts
        try:
            alert_sync_payload = None
            effective_status = str(updated_item.get("status") or next_status or existing.get("status") or "").lower()
            if effective_status in {"assigned", "in_progress"}:
                alert_sync_payload = {"status": "acknowledged", "resolved_at": None}
            elif effective_status == "resolved":
                alert_sync_payload = {
                    "status": "resolved",
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
            elif effective_status == "dismissed":
                alert_sync_payload = {
                    "status": "dismissed",
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
            elif effective_status == "open":
                alert_sync_payload = {"status": "open", "resolved_at": None}

            if alert_sync_payload:
                if "assigned_user_id" in update_payload:
                    alert_sync_payload["assigned_user_id"] = update_payload.get("assigned_user_id")
                (
                    supabase.table("conversation_alerts")
                    .update(alert_sync_payload)
                    .eq("client_id", payload.client_id)
                    .eq("source_handoff_request_id", handoff_id)
                    .execute()
                )
        except Exception as sync_error:
            logger.warning("Could not sync conversation_alerts for handoff %s: %s", handoff_id, sync_error)

        # Best-effort sync: conversation status
        try:
            conversation_id = updated_item.get("conversation_id") or existing.get("conversation_id")
            if conversation_id:
                convo_status_map = {
                    "open": "needs_human",
                    "assigned": "needs_human",
                    "in_progress": "human_in_progress",
                    "resolved": "resolved",
                    "dismissed": "closed",
                }
                effective_status = str(updated_item.get("status") or next_status or "").lower()
                convo_status = convo_status_map.get(effective_status)
                if convo_status:
                    convo_update = {
                        "status": convo_status,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if "assigned_user_id" in update_payload:
                        convo_update["assigned_user_id"] = update_payload.get("assigned_user_id")
                    (
                        supabase.table("conversations")
                        .update(convo_update)
                        .eq("id", conversation_id)
                        .eq("client_id", payload.client_id)
                        .execute()
                    )
        except Exception as convo_sync_error:
            logger.warning("Could not sync conversations for handoff %s: %s", handoff_id, convo_sync_error)

        return {"success": True, "item": updated_item}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating conversation handoff request")
        raise HTTPException(status_code=500, detail=f"Conversation handoff update error: {e}")
