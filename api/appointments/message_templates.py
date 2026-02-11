from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
import uuid
import logging

from api.config.config import supabase

logger = logging.getLogger(__name__)

# ======================================
# Router
# ======================================
router = APIRouter(
    prefix="/message_templates",
    tags=["Message Templates"]
)

# ======================================
# Models
# ======================================

class ReminderRule(BaseModel):
    offset_minutes: int = Field(
        ...,
        description="Minutes before appointment (negative number)"
    )
    label: Optional[str] = None


class CreateTemplatePayload(BaseModel):
    client_id: uuid.UUID

    channel: Literal["whatsapp", "email"]

    # 🔑 REQUIRED — DB constraint
    type: Literal[
        "appointment_reminder",
        "appointment_confirmation",
        "appointment_cancellation"
    ]

    # WhatsApp (Meta only)
    meta_template_name: Optional[str] = Field(None, min_length=3)

    # Email / custom channels
    body: Optional[str] = Field(None, min_length=5)

    label: Optional[str] = None
    frequency: Optional[List[ReminderRule]] = None
    is_active: bool = True


class UpdateTemplatePayload(BaseModel):
    label: Optional[str] = None
    body: Optional[str] = Field(None, min_length=5)
    frequency: Optional[List[ReminderRule]] = None
    is_active: Optional[bool] = None


# ======================================
# CREATE TEMPLATE
# ======================================
@router.post("")
def create_message_template(payload: CreateTemplatePayload):
    """
    Create message templates.

    Rules:
    - WhatsApp templates must reference Meta-approved templates
    - Email templates are fully editable
    - `type` is REQUIRED (DB constraint)
    - Frequency validated if provided
    """

    # =========================
    # Channel-specific validation
    # =========================
    if payload.channel == "whatsapp":
        if not payload.meta_template_name:
            raise HTTPException(
                status_code=400,
                detail="meta_template_name is required for WhatsApp templates"
            )

        meta_template = (
            supabase
            .table("meta_approved_templates")
            .select("template_name")
            .eq("template_name", payload.meta_template_name)
            .eq("is_active", True)
            .single()
            .execute()
        )

        if not meta_template.data:
            raise HTTPException(
                status_code=400,
                detail="Meta template not found or inactive"
            )

        # WhatsApp never stores body
        body = None

    elif payload.channel == "email":
        if not payload.body:
            raise HTTPException(
                status_code=400,
                detail="body is required for email templates"
            )

        body = payload.body

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid channel"
        )

    # =========================
    # Frequency validation
    # =========================
    if payload.frequency:
        for rule in payload.frequency:
            if rule.offset_minutes >= 0:
                raise HTTPException(
                    status_code=400,
                    detail="offset_minutes must be negative"
                )

    # =========================
    # Insert
    # =========================
    template_data = {
        "client_id": str(payload.client_id),
        "channel": payload.channel,
        "type": payload.type,
        "template_name": (
            payload.meta_template_name
            if payload.channel == "whatsapp"
            else None
        ),
        "label": payload.label,
        "body": body,
        "frequency": (
            [rule.dict() for rule in payload.frequency]
            if payload.frequency else None
        ),
        "is_active": payload.is_active,
    }

    res = (
        supabase
        .table("message_templates")
        .insert(template_data)
        .execute()
    )

    if not res.data:
        logger.error("❌ Failed to create message template")
        raise HTTPException(
            status_code=500,
            detail="Failed to create message template"
        )

    return {
        "success": True,
        "template": res.data[0],
    }


# ======================================
# UPDATE TEMPLATE
# ======================================
@router.put("/{template_id}")
def update_message_template(
    template_id: uuid.UUID,
    payload: UpdateTemplatePayload,
):
    """
    Update message template.

    Rules:
    - WhatsApp templates cannot change body or template_name
    - Email templates can update body
    - Frequency and label are always allowed
    """

    update_data = payload.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided to update"
        )

    # Load existing template
    existing = (
        supabase
        .table("message_templates")
        .select("channel")
        .eq("id", str(template_id))
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Template not found"
        )

    channel = existing.data["channel"]

    # Guard rails
    if channel == "whatsapp" and "body" in update_data:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp templates cannot update body"
        )

    # Validate frequency
    if "frequency" in update_data:
        if update_data["frequency"]:
            for rule in update_data["frequency"]:
                offset = rule.get("offset_minutes")
                if offset is None or offset >= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="offset_minutes must be negative"
                    )
        else:
            update_data["frequency"] = None

    update_data["updated_at"] = "now()"

    res = (
        supabase
        .table("message_templates")
        .update(update_data)
        .eq("id", str(template_id))
        .execute()
    )

    if not res.data:
        raise HTTPException(
            status_code=404,
            detail="Template not found"
        )

    return {
        "success": True,
        "template": res.data[0],
    }


# ======================================
# DELETE TEMPLATE (SOFT DELETE)
# ======================================
@router.delete("/{template_id}")
def delete_message_template(template_id: uuid.UUID):
    """
    Soft delete a message template.
    Existing reminders are NOT affected.
    """

    res = (
        supabase
        .table("message_templates")
        .update({
            "is_active": False,
            "updated_at": "now()"
        })
        .eq("id", str(template_id))
        .execute()
    )

    if not res.data:
        raise HTTPException(
            status_code=404,
            detail="Template not found"
        )

    return {
        "success": True,
        "message": "Template deactivated",
    }
