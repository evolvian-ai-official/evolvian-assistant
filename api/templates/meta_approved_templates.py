from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging

from api.authz import authorize_client_request
from api.config.config import supabase
from api.modules.whatsapp.template_sync import (
    build_client_template_name,
    estimate_template_pricing,
    get_client_country_code,
    get_client_template_sync_map,
    infer_template_category,
    refresh_client_template_statuses,
    sync_canonical_templates_for_client,
)
from api.security.request_limiter import enforce_rate_limit, get_request_ip

logger = logging.getLogger(__name__)

# ======================================
# Router
# ======================================
router = APIRouter(
    prefix="/meta_approved_templates",
    tags=["Meta Approved Templates"]
)

# ======================================
# Response Model
# ======================================
class MetaApprovedTemplateResponse(BaseModel):
    id: str
    template_name: str
    preview_body: Optional[str] = None
    language: str
    parameter_count: int
    type: str
    category: Optional[str] = None

    # Client-specific fields
    client_template_name: Optional[str] = None
    client_template_status: Optional[str] = None
    client_template_active: Optional[bool] = None

    # Pricing estimate
    pricing_currency: Optional[str] = None
    estimated_unit_cost: Optional[float] = None
    billable: Optional[bool] = None
    pricing_source: Optional[str] = None
    pricing_disclaimer: Optional[str] = None


# ======================================
# Endpoint
# ======================================
@router.get("", response_model=List[MetaApprovedTemplateResponse])
def get_meta_approved_templates(
    request: Request,
    type: Optional[str] = Query(None, description="Template functional type"),
    channel: Optional[str] = Query("whatsapp", description="Channel type"),
    client_id: Optional[str] = Query(
        None,
        description="Optional client_id to resolve per-account status/cost",
    ),
    only_active_for_client: bool = Query(
        False,
        description="When client_id is provided, return only active templates for that account",
    ),
    refresh_status: bool = Query(
        False,
        description="When client_id is provided, refresh local status from Meta before returning data",
    ),
):
    """
    Read-only list of Evolvian Meta-approved templates.
    Filters are optional and validated dynamically.
    """

    logger.info(f"📥 Fetching Meta templates | type={type} | channel={channel}")

    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="meta_templates_ip",
            key=request_ip,
            limit=180,
            window_seconds=60,
        )

        # ======================================
        # Validate type dynamically (if provided)
        # ======================================
        if type:
            type_check = (
                supabase
                .table("template_types")
                .select("id")
                .eq("id", type)
                .single()
                .execute()
            )

            if not type_check.data:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid template type"
                )

        # ======================================
        # Validate channel (basic safety)
        # ======================================
        if channel and channel not in ["whatsapp", "email"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid channel"
            )

        if client_id:
            authorize_client_request(request, client_id)

            if refresh_status:
                if channel == "whatsapp":
                    summary = sync_canonical_templates_for_client(
                        client_id=client_id,
                        force_refresh=False,
                    )
                    if not summary.get("success"):
                        logger.warning(
                            "⚠️ Meta template sync returned warnings | client_id=%s | errors=%s",
                            client_id,
                            summary.get("errors"),
                        )
                else:
                    refresh_client_template_statuses(client_id=client_id)

        # ======================================
        # Query canonical catalog
        # ======================================
        query = (
            supabase
            .table("meta_approved_templates")
            .select(
                "id, template_name, preview_body, language, parameter_count, type"
            )
            .eq("is_active", True)
        )

        if type:
            query = query.eq("type", type)

        if channel:
            query = query.eq("channel", channel)

        res = query.order("template_name").execute()

        templates = res.data or []

        if not client_id:
            return templates

        sync_map = get_client_template_sync_map(client_id)
        if channel == "whatsapp" and templates and not sync_map:
            logger.info(
                "ℹ️ client_whatsapp_templates empty; attempting bootstrap sync | client_id=%s",
                client_id,
            )
            bootstrap = sync_canonical_templates_for_client(
                client_id=client_id,
                force_refresh=False,
            )
            if not bootstrap.get("success"):
                logger.warning(
                    "⚠️ Bootstrap sync returned warnings | client_id=%s | errors=%s",
                    client_id,
                    bootstrap.get("errors"),
                )
            sync_map = get_client_template_sync_map(client_id)

        country_code = get_client_country_code(client_id)
        formatted: list[MetaApprovedTemplateResponse] = []

        for template in templates:
            template_id = str(template.get("id") or "")
            template_type = template.get("type")
            category = infer_template_category(template_type)
            pricing = estimate_template_pricing(
                category=category,
                country_code=country_code,
            )

            synced = sync_map.get(template_id)
            client_template_name = (
                synced.get("meta_template_name")
                if synced else build_client_template_name(template.get("template_name") or "template", client_id)
            )
            client_template_status = synced.get("status") if synced else "not_synced"
            client_template_active = bool(synced.get("is_active")) if synced else False

            if only_active_for_client and not client_template_active:
                continue

            estimated_cost = synced.get("estimated_unit_cost") if synced else pricing["unit_cost_estimate"]
            if estimated_cost is None:
                estimated_cost = pricing["unit_cost_estimate"]

            formatted.append(
                MetaApprovedTemplateResponse(
                    id=template_id,
                    template_name=template.get("template_name"),
                    preview_body=template.get("preview_body"),
                    language=template.get("language"),
                    parameter_count=int(template.get("parameter_count") or 0),
                    type=template_type,
                    category=synced.get("category") if synced else category,
                    client_template_name=client_template_name,
                    client_template_status=client_template_status,
                    client_template_active=client_template_active,
                    pricing_currency=(
                        synced.get("pricing_currency")
                        if synced and synced.get("pricing_currency")
                        else pricing["currency"]
                    ),
                    estimated_unit_cost=float(estimated_cost or 0),
                    billable=(
                        bool(synced.get("billable"))
                        if synced and synced.get("billable") is not None
                        else pricing["billable"]
                    ),
                    pricing_source=(
                        synced.get("pricing_source")
                        if synced and synced.get("pricing_source")
                        else pricing["pricing_source"]
                    ),
                    pricing_disclaimer=pricing["pricing_disclaimer"],
                )
            )

        return formatted

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error fetching meta templates")
        raise HTTPException(status_code=500, detail="Internal server error")
