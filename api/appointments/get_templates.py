from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
import uuid
import logging

from api.authz import authorize_client_request
from api.config.config import supabase
from api.modules.whatsapp.template_sync import (
    build_client_template_name,
    estimate_template_pricing,
    get_client_country_code,
    get_client_template_sync_map,
    infer_template_category,
)

logger = logging.getLogger(__name__)

# =========================
# Router
# =========================
router = APIRouter(
    prefix="/message_templates",
    tags=["Message Templates"]
)

# =========================
# Frequency Model
# =========================
class FrequencyRule(BaseModel):
    offset_minutes: int
    label: Optional[str] = None


# =========================
# Response Model
# =========================
class MessageTemplateResponse(BaseModel):
    id: uuid.UUID
    channel: str
    type: str
    is_active: bool = True

    # Email only
    body: Optional[str] = None

    # Snapshot name (local)
    template_name: Optional[str] = None

    # Meta resolved
    meta_template_name: Optional[str] = None
    meta_parameter_count: Optional[int] = None
    meta_language: Optional[str] = None
    meta_preview_body: Optional[str] = None

    label: Optional[str] = None
    frequency: Optional[List[FrequencyRule]] = None

    is_meta_template: bool
    template_category: Optional[str] = None
    whatsapp_client_template_name: Optional[str] = None
    whatsapp_template_status: Optional[str] = None
    whatsapp_template_active: Optional[bool] = None
    pricing_currency: Optional[str] = None
    estimated_unit_cost: Optional[float] = None
    billable: Optional[bool] = None
    pricing_source: Optional[str] = None
    pricing_disclaimer: Optional[str] = None


# =========================
# Endpoint
# =========================
@router.get("", response_model=List[MessageTemplateResponse])
def get_message_templates(
    request: Request,
    client_id: uuid.UUID = Query(..., description="Client ID"),
    type: Optional[str] = Query(
        None,
        description="appointment_reminder | appointment_confirmation | appointment_cancellation"
    ),
    include_inactive: bool = Query(False),
):
    """
    Returns active message templates for a client.

    WhatsApp templates are resolved manually against meta_approved_templates.
    Meta is the source of truth.
    """

    try:
        authorize_client_request(request, str(client_id))

        # --------------------------
        # 1️⃣ Fetch message templates
        # --------------------------
        query = (
            supabase
            .table("message_templates")
            .select(
                "id, channel, type, is_active, body, frequency, template_name, label, meta_template_id"
            )
            .eq("client_id", str(client_id))
        )

        if not include_inactive:
            query = query.eq("is_active", True)

        if type:
            query = query.eq("type", type)

        res = query.order("template_name").execute()

        if not hasattr(res, "data"):
            logger.error("Supabase returned malformed response")
            raise HTTPException(status_code=500, detail="Database error")

        templates = res.data or []
        client_id_str = str(client_id)
        sync_map = get_client_template_sync_map(client_id_str)
        country_code = get_client_country_code(client_id_str)

        formatted_templates: List[MessageTemplateResponse] = []

        # --------------------------
        # 2️⃣ Resolve Meta manually
        # --------------------------
        for t in templates:

            meta = None

            if t.get("meta_template_id"):

                meta_res = (
                    supabase
                    .table("meta_approved_templates")
                    .select(
                        "template_name, parameter_count, language, preview_body"
                    )
                    .eq("id", t["meta_template_id"])
                    .eq("is_active", True)
                    .single()
                    .execute()
                )

                meta = meta_res.data if hasattr(meta_res, "data") else None

                if not meta:
                    logger.warning(
                        f"Meta template not found or inactive: {t['meta_template_id']}"
                    )

            is_meta = bool(meta)
            is_whatsapp = t.get("channel") == "whatsapp"
            meta_template_id = str(t.get("meta_template_id") or "")

            if is_whatsapp and not meta_template_id:
                logger.warning(
                    "⚠️ Skipping legacy WhatsApp template without canonical meta_template_id | template_id=%s",
                    t.get("id"),
                )
                continue

            if is_whatsapp and not meta:
                logger.warning(
                    "⚠️ Skipping WhatsApp template with missing canonical meta_approved_templates row | template_id=%s | meta_template_id=%s",
                    t.get("id"),
                    meta_template_id,
                )
                continue

            sync_row = sync_map.get(meta_template_id) if meta_template_id else None
            category = infer_template_category(t.get("type"))
            pricing = estimate_template_pricing(
                category=sync_row.get("category") if sync_row else category,
                country_code=country_code,
            )
            estimated_unit_cost = (
                sync_row.get("estimated_unit_cost")
                if sync_row and sync_row.get("estimated_unit_cost") is not None
                else pricing["unit_cost_estimate"]
            )
            pricing_currency = (
                sync_row.get("pricing_currency")
                if sync_row and sync_row.get("pricing_currency")
                else pricing["currency"]
            )
            billable = (
                bool(sync_row.get("billable"))
                if sync_row and sync_row.get("billable") is not None
                else pricing["billable"]
            )
            pricing_source = (
                sync_row.get("pricing_source")
                if sync_row and sync_row.get("pricing_source")
                else pricing["pricing_source"]
            )

            formatted_templates.append(
                MessageTemplateResponse(
                    id=t["id"],
                    channel=t["channel"],
                    type=t["type"],
                    is_active=bool(t.get("is_active", True)),

                    # 🔒 WhatsApp never exposes body
                    body=None if is_whatsapp else t.get("body"),

                    template_name=t.get("template_name"),

                    meta_template_name=meta.get("template_name") if meta else None,
                    meta_parameter_count=meta.get("parameter_count") if meta else None,
                    meta_language=meta.get("language") if meta else None,
                    meta_preview_body=meta.get("preview_body") if meta else None,

                    label=t.get("label"),
                    frequency=t.get("frequency"),

                    is_meta_template=is_meta,
                    template_category=category if is_whatsapp else None,
                    whatsapp_client_template_name=(
                        sync_row.get("meta_template_name")
                        if sync_row
                        else (
                            build_client_template_name(
                                meta.get("template_name") if meta else (t.get("template_name") or "template"),
                                client_id_str,
                            )
                            if is_whatsapp else None
                        )
                    ),
                    whatsapp_template_status=(
                        sync_row.get("status") if sync_row else ("not_synced" if is_whatsapp else None)
                    ),
                    whatsapp_template_active=(
                        bool(sync_row.get("is_active"))
                        if sync_row
                        else (False if is_whatsapp else None)
                    ),
                    pricing_currency=pricing_currency if is_whatsapp else None,
                    estimated_unit_cost=float(estimated_unit_cost or 0) if is_whatsapp else None,
                    billable=billable if is_whatsapp else None,
                    pricing_source=pricing_source if is_whatsapp else None,
                    pricing_disclaimer=pricing["pricing_disclaimer"] if is_whatsapp else None,
                )
            )

        return formatted_templates

    except HTTPException:
        raise

    except Exception:
        logger.exception("Failed to fetch message templates")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch message templates"
        )
