from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
import logging

from api.authz import authorize_client_request
from api.config.config import supabase
from api.modules.whatsapp.template_sync import (
    get_client_template_sync_map,
    refresh_client_template_statuses,
    sync_canonical_templates_for_client,
)

router = APIRouter(prefix="/templates", tags=["WhatsApp Template Sync"])
logger = logging.getLogger(__name__)


class SyncTemplatesPayload(BaseModel):
    client_id: str
    force_refresh: bool = False


@router.post("/sync")
def sync_templates(payload: SyncTemplatesPayload, request: Request):
    try:
        authorize_client_request(request, payload.client_id)
        summary = sync_canonical_templates_for_client(
            client_id=payload.client_id,
            force_refresh=payload.force_refresh,
        )
        return summary
    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ Failed syncing WhatsApp templates")
        raise HTTPException(status_code=500, detail="Failed syncing WhatsApp templates")


@router.post("/refresh_status")
def refresh_templates_status(payload: SyncTemplatesPayload, request: Request):
    try:
        authorize_client_request(request, payload.client_id)
        summary = refresh_client_template_statuses(client_id=payload.client_id)
        return summary
    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ Failed refreshing WhatsApp template statuses")
        raise HTTPException(status_code=500, detail="Failed refreshing WhatsApp template statuses")


@router.get("/status")
def get_templates_status(
    request: Request,
    client_id: str = Query(...),
):
    try:
        authorize_client_request(request, client_id)

        try:
            response = (
                supabase
                .table("client_whatsapp_templates")
                .select(
                    "meta_template_id,meta_template_name,status,is_active,category,language,"
                    "status_reason,last_synced_at,pricing_currency,estimated_unit_cost,"
                    "billable,pricing_source,meta_approved_templates("
                    "template_name,preview_body,parameter_count,type)"
                )
                .eq("client_id", client_id)
                .order("meta_template_name")
                .execute()
            )

            data = response.data or []
            return {
                "client_id": client_id,
                "templates": data,
                "count": len(data),
            }
        except Exception:
            # If migration is not applied yet, return graceful empty state.
            logger.exception("⚠️ client_whatsapp_templates query failed")
            fallback = get_client_template_sync_map(client_id)
            rows = list(fallback.values())
            return {
                "client_id": client_id,
                "templates": rows,
                "count": len(rows),
                "warning": "client_whatsapp_templates table unavailable",
            }

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ Failed loading WhatsApp template statuses")
        raise HTTPException(status_code=500, detail="Failed loading WhatsApp template statuses")
