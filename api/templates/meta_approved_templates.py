from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from api.config.config import supabase

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
    preview_body: str
    language: str
    parameter_count: int
    type: str


# ======================================
# Endpoint
# ======================================
@router.get("", response_model=List[MetaApprovedTemplateResponse])
def get_meta_approved_templates(
    type: Optional[str] = Query(None, description="Template functional type"),
    channel: Optional[str] = Query("whatsapp", description="Channel type")
):
    """
    Read-only list of Evolvian Meta-approved templates.
    Filters are optional and validated dynamically.
    """

    logger.info(f"📥 Fetching Meta templates | type={type} | channel={channel}")

    try:

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

        # ======================================
        # Query
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

        return res.data or []

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error fetching meta templates")
        raise HTTPException(status_code=500, detail="Internal server error")
