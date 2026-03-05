from datetime import datetime, timezone
import logging
import json
import re
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


class ConvertProspectToClientInput(BaseModel):
    client_id: str


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    if digits.startswith("521") and len(digits) == 13:
        digits = "52" + digits[3:]
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}"


def _normalize_name(value: Optional[str]) -> Optional[str]:
    cleaned = " ".join(str(value or "").strip().split())
    return cleaned or None


def _coerce_metadata(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _is_missing_appointment_clients_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "appointment_clients" in msg and (
        "does not exist" in msg or "relation" in msg or "schema cache" in msg or "not found" in msg
    )


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


@router.post("/conversation_handoff_requests/{handoff_id}/convert_to_client")
def convert_prospect_to_client(
    handoff_id: str,
    payload: ConvertProspectToClientInput,
    request: Request,
):
    try:
        authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")

        handoff_res = (
            supabase.table("conversation_handoff_requests")
            .select(
                "id,client_id,conversation_id,status,trigger,reason,contact_name,contact_email,"
                "contact_phone,metadata"
            )
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .maybe_single()
            .execute()
        )
        handoff = handoff_res.data if handoff_res else None
        if not handoff:
            raise HTTPException(status_code=404, detail="Handoff request not found")

        reason = str(handoff.get("reason") or "").strip().lower()
        trigger = str(handoff.get("trigger") or "").strip().lower()
        is_prospect = reason == "campaign_interest" or trigger == "campaign_interest_button"
        if not is_prospect:
            raise HTTPException(status_code=409, detail="This handoff is not a campaign prospect")

        user_name = _normalize_name(handoff.get("contact_name")) or "Client"
        user_email = _normalize_email(handoff.get("contact_email"))
        user_phone = _normalize_phone(handoff.get("contact_phone"))
        if not user_email and not user_phone:
            raise HTTPException(status_code=422, detail="Prospect has no valid email or phone to create client record")

        now_iso = datetime.now(timezone.utc).isoformat()
        existing = None
        if user_email:
            existing_email_res = (
                supabase.table("appointment_clients")
                .select("*")
                .eq("client_id", payload.client_id)
                .eq("normalized_email", user_email)
                .limit(1)
                .execute()
            )
            existing = (existing_email_res.data or [None])[0]
        if not existing and user_phone:
            existing_phone_res = (
                supabase.table("appointment_clients")
                .select("*")
                .eq("client_id", payload.client_id)
                .eq("normalized_phone", user_phone)
                .limit(1)
                .execute()
            )
            existing = (existing_phone_res.data or [None])[0]

        clean_payload = {
            "user_name": user_name,
            "user_email": user_email,
            "user_phone": user_phone,
            "normalized_email": user_email,
            "normalized_phone": user_phone,
        }
        if existing:
            update_payload = {**clean_payload, "updated_at": now_iso}
            if "deleted_at" in existing:
                update_payload["deleted_at"] = None
            client_row_res = (
                supabase.table("appointment_clients")
                .update(update_payload)
                .eq("id", existing["id"])
                .eq("client_id", payload.client_id)
                .execute()
            )
            client_row = (client_row_res.data or [None])[0]
        else:
            client_row_res = (
                supabase.table("appointment_clients")
                .insert(
                    {
                        "client_id": payload.client_id,
                        **clean_payload,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                )
                .execute()
            )
            client_row = (client_row_res.data or [None])[0]

        if not client_row:
            raise HTTPException(status_code=500, detail="Unable to create/update appointment client record")

        metadata = _coerce_metadata(handoff.get("metadata"))
        metadata.update(
            {
                "lifecycle_stage": "client",
                "converted_to_client": True,
                "converted_to_client_at": now_iso,
                "appointment_client_id": client_row.get("id"),
            }
        )

        handoff_update_res = (
            supabase.table("conversation_handoff_requests")
            .update({"metadata": metadata, "updated_at": now_iso})
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        updated_handoff = (handoff_update_res.data or [None])[0] or handoff

        conversation_id = handoff.get("conversation_id")
        if conversation_id:
            try:
                (
                    supabase.table("conversations")
                    .update(
                        {
                            "contact_name": user_name,
                            "contact_email": user_email,
                            "contact_phone": user_phone,
                            "updated_at": now_iso,
                        }
                    )
                    .eq("id", conversation_id)
                    .eq("client_id", payload.client_id)
                    .execute()
                )
            except Exception as convo_sync_error:
                logger.warning("Could not sync conversation contact info for handoff %s: %s", handoff_id, convo_sync_error)

        return {
            "success": True,
            "handoff_id": handoff_id,
            "appointment_client": client_row,
            "handoff": updated_handoff,
        }
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_appointment_clients_table(e):
            raise HTTPException(
                status_code=503,
                detail="appointment_clients table is not available yet. Run the SQL migration first.",
            )
        logger.exception("Error converting prospect to client")
        raise HTTPException(status_code=500, detail=f"Conversation prospect conversion error: {e}")
