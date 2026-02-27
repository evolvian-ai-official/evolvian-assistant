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


def _is_campaign_meta_type(template_type: Optional[str]) -> bool:
    probe = str(template_type or "").strip().lower()
    return probe.startswith("campaign_whatsapp")


def _normalize_visibility_scope(row: dict) -> str:
    raw = str((row or {}).get("visibility_scope") or "").strip().lower()
    if raw in {"global", "client_private"}:
        return raw
    return ""


def _normalize_owner_client_id(row: dict) -> Optional[str]:
    value = str((row or {}).get("owner_client_id") or "").strip()
    return value or None


def _is_private_template_row(row: dict) -> bool:
    scope = _normalize_visibility_scope(row)
    if scope == "client_private":
        return True
    if scope == "global":
        return False
    # Legacy fallback before visibility_scope existed.
    return _is_campaign_meta_type((row or {}).get("type"))


def _load_client_owned_campaign_meta_ids(*, client_id: str, candidate_ids: list[str]) -> set[str]:
    ids = [str(value or "").strip() for value in candidate_ids if str(value or "").strip()]
    if not ids:
        return set()
    try:
        try:
            res = (
                supabase
                .table("message_templates")
                .select("meta_template_id,type")
                .eq("client_id", client_id)
                .eq("channel", "whatsapp")
                .eq("variant_key", "campaign")
                .eq("is_active", True)
                .in_("meta_template_id", ids)
                .execute()
            )
        except Exception:
            # Fallback for environments where variant_key is not available yet.
            res = (
                supabase
                .table("message_templates")
                .select("meta_template_id,type")
                .eq("client_id", client_id)
                .eq("channel", "whatsapp")
                .eq("is_active", True)
                .in_("meta_template_id", ids)
                .execute()
            )
        return {
            str((row or {}).get("meta_template_id") or "").strip()
            for row in (res.data or [])
            if str((row or {}).get("meta_template_id") or "").strip()
            and _is_campaign_meta_type((row or {}).get("type"))
        }
    except Exception:
        logger.exception("❌ Failed loading campaign template ownership for catalog | client_id=%s", client_id)
        return set()


def _filter_templates_visibility(templates: list[dict], *, client_id: Optional[str]) -> list[dict]:
    if not templates:
        return []

    visible_rows: list[dict] = []
    unresolved_private_rows: list[dict] = []

    for row in templates:
        template = row or {}
        scope = _normalize_visibility_scope(template)
        owner_client_id = _normalize_owner_client_id(template)

        if scope == "global":
            visible_rows.append(template)
            continue

        if scope == "client_private":
            if client_id and owner_client_id and str(owner_client_id) == str(client_id):
                visible_rows.append(template)
            elif not owner_client_id:
                # Defensive fallback for partially backfilled rows.
                unresolved_private_rows.append(template)
            continue

        if _is_private_template_row(template):
            unresolved_private_rows.append(template)
        else:
            visible_rows.append(template)

    if not unresolved_private_rows:
        return visible_rows
    if not client_id:
        return visible_rows

    fallback_ids = [str((row or {}).get("id") or "").strip() for row in unresolved_private_rows]
    owned_ids = _load_client_owned_campaign_meta_ids(client_id=client_id, candidate_ids=fallback_ids)
    if not owned_ids:
        return visible_rows

    owned_rows = [
        row for row in unresolved_private_rows
        if str((row or {}).get("id") or "").strip() in owned_ids
    ]
    return [*visible_rows, *owned_rows]


def _load_meta_catalog_rows(*, channel: Optional[str], type: Optional[str]) -> list[dict]:
    select_attempts = [
        "id, template_name, preview_body, language, parameter_count, type, owner_client_id, visibility_scope",
        "id, template_name, preview_body, language, parameter_count, type",
    ]

    for select_fields in select_attempts:
        try:
            query = (
                supabase
                .table("meta_approved_templates")
                .select(select_fields)
                .eq("is_active", True)
            )
            if type:
                query = query.eq("type", type)
            if channel:
                query = query.eq("channel", channel)
            return query.order("template_name").execute().data or []
        except Exception:
            continue

    raise HTTPException(status_code=500, detail="Internal server error")


# ======================================
# Endpoint
# ======================================
@router.get("", response_model=List[MetaApprovedTemplateResponse])
def get_meta_approved_templates(
    request: Request,
    type: Optional[str] = Query(None, description="Template functional type"),
    channel: Optional[str] = Query("whatsapp", description="Channel type"),
    language_family: Optional[str] = Query(None, description="Language family filter (es|en)"),
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

    logger.info(
        "📥 Fetching Meta templates | type=%s | channel=%s | language_family=%s",
        type,
        channel,
        language_family,
    )

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
        if language_family and str(language_family).lower() not in {"es", "en"}:
            raise HTTPException(status_code=400, detail="Invalid language_family")

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
        templates = _filter_templates_visibility(
            _load_meta_catalog_rows(channel=channel, type=type),
            client_id=client_id,
        )
        if language_family:
            family = str(language_family).strip().lower()
            templates = [
                row for row in templates
                if str((row or {}).get("language") or "").lower().startswith(family)
            ]

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
