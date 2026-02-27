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

ALERT_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}


class ConversationAlertUpdateInput(BaseModel):
    client_id: str
    status: str


@router.get("/conversation_alerts")
def list_conversation_alerts(
    request: Request,
    client_id: str = Query(...),
    status: str = Query("open"),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        authorize_client_request(request, client_id)
        require_client_feature(client_id, "handoff", required_plan_label="premium")

        status_filter = (status or "open").strip().lower()
        if status_filter != "all" and status_filter not in ALERT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")

        query = (
            supabase.table("conversation_alerts")
            .select(
                "id,client_id,conversation_id,source_handoff_request_id,alert_type,status,priority,"
                "assigned_user_id,title,body,metadata,created_at,resolved_at"
            )
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status_filter != "all":
            query = query.eq("status", status_filter)

        alerts_res = query.execute()
        alerts = alerts_res.data or []

        handoff_ids = [a.get("source_handoff_request_id") for a in alerts if a.get("source_handoff_request_id")]
        handoff_map = {}
        if handoff_ids:
            try:
                handoff_res = (
                    supabase.table("conversation_handoff_requests")
                    .select(
                        "id,session_id,channel,trigger,reason,confidence_score,contact_name,contact_email,"
                        "contact_phone,accepted_terms,accepted_email_marketing,last_user_message,last_ai_message,"
                        "created_at,status,assigned_user_id,internal_resolution_note,resolved_at,updated_at,metadata"
                    )
                    .in_("id", handoff_ids)
                    .execute()
                )
                handoff_map = {row.get("id"): row for row in (handoff_res.data or []) if row.get("id")}
            except Exception as handoff_error:
                logger.warning("Could not enrich conversation alerts with handoff data: %s", handoff_error)

        for alert in alerts:
            source_handoff_id = alert.get("source_handoff_request_id")
            if source_handoff_id and source_handoff_id in handoff_map:
                alert["handoff"] = handoff_map[source_handoff_id]

        counts = {}
        try:
            for s in ("open", "acknowledged", "resolved"):
                count_res = (
                    supabase.table("conversation_alerts")
                    .select("id", count="exact")
                    .eq("client_id", client_id)
                    .eq("status", s)
                    .limit(1)
                    .execute()
                )
                counts[s] = getattr(count_res, "count", 0) or 0
        except Exception as count_error:
            logger.warning("Could not load conversation alert counts: %s", count_error)

        return {"items": alerts, "counts": counts, "status_filter": status_filter}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing conversation alerts")
        raise HTTPException(status_code=500, detail=f"Conversation alerts error: {e}")


@router.patch("/conversation_alerts/{alert_id}")
def update_conversation_alert(
    alert_id: str,
    payload: ConversationAlertUpdateInput,
    request: Request,
):
    try:
        authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")
        next_status = (payload.status or "").strip().lower()
        if next_status not in ALERT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid alert status")

        existing_res = (
            supabase.table("conversation_alerts")
            .select("id,status,client_id")
            .eq("id", alert_id)
            .eq("client_id", payload.client_id)
            .maybe_single()
            .execute()
        )
        if not existing_res or not existing_res.data:
            raise HTTPException(status_code=404, detail="Alert not found")

        update_payload = {"status": next_status}
        if next_status in {"resolved", "dismissed"}:
            update_payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
        else:
            update_payload["resolved_at"] = None

        updated_res = (
            supabase.table("conversation_alerts")
            .update(update_payload)
            .eq("id", alert_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        updated_rows = updated_res.data or []
        return {"success": True, "item": updated_rows[0] if updated_rows else {"id": alert_id, **update_payload}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating conversation alert")
        raise HTTPException(status_code=500, detail=f"Conversation alert update error: {e}")
