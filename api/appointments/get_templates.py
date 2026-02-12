from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import uuid
import logging

from api.config.config import supabase

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


# =========================
# Endpoint
# =========================
@router.get("", response_model=List[MessageTemplateResponse])
def get_message_templates(
    client_id: uuid.UUID = Query(..., description="Client ID"),
    type: Optional[str] = Query(
        None,
        description="appointment_reminder | appointment_confirmation | appointment_cancellation"
    ),
):
    """
    Returns active message templates for a client.

    WhatsApp templates are resolved manually against meta_approved_templates.
    Meta is the source of truth.
    """

    try:

        # --------------------------
        # 1️⃣ Fetch message templates
        # --------------------------
        query = (
            supabase
            .table("message_templates")
            .select(
                "id, channel, type, body, frequency, template_name, label, meta_template_id"
            )
            .eq("client_id", str(client_id))
            .eq("is_active", True)
        )

        if type:
            query = query.eq("type", type)

        res = query.order("template_name").execute()

        if not hasattr(res, "data"):
            logger.error("Supabase returned malformed response")
            raise HTTPException(status_code=500, detail="Database error")

        templates = res.data or []

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

            formatted_templates.append(
                MessageTemplateResponse(
                    id=t["id"],
                    channel=t["channel"],
                    type=t["type"],

                    # 🔒 WhatsApp never exposes body
                    body=None if t["channel"] == "whatsapp" else t.get("body"),

                    template_name=t.get("template_name"),

                    meta_template_name=meta.get("template_name") if meta else None,
                    meta_parameter_count=meta.get("parameter_count") if meta else None,
                    meta_language=meta.get("language") if meta else None,
                    meta_preview_body=meta.get("preview_body") if meta else None,

                    label=t.get("label"),
                    frequency=t.get("frequency"),

                    is_meta_template=is_meta
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
