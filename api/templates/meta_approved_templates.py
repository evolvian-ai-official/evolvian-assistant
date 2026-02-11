from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
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
    template_name: str
    preview_body: str
    language: str
    parameter_count: int

# ======================================
# Endpoint
# ======================================
@router.get("", response_model=List[MetaApprovedTemplateResponse])
def get_meta_approved_templates():
    """
    Read-only list of Meta-approved WhatsApp templates.
    Used for dropdown selection in UI.
    """

    logger.info("📥 Fetching Meta approved templates")

    res = (
        supabase
        .table("meta_approved_templates")
        .select(
            "template_name, preview_body, language, parameter_count"
        )
        .eq("is_active", True)
        .order("template_name")
        .execute()
    )

    return res.data or []
