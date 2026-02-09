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
    type: Literal[
        "appointment_reminder",
        "appointment_confirmation",
        "appointment_cancellation"
    ]

    template_name: str = Field(..., min_length=3)
    label: Optional[str] = None
    body: str = Field(..., min_length=5)

    frequency: Optional[List[ReminderRule]] = None
    is_active: bool = True


class UpdateTemplatePayload(BaseModel):
    template_name: Optional[str] = Field(None, min_length=3)
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
    Frequency is only allowed for appointment_reminder.
    """

    # =========================
    # Validations
    # =========================
    if payload.type == "appointment_reminder":
        if not payload.frequency:
            raise HTTPException(
                status_code=400,
                detail="frequency is required for appointment_reminder templates"
            )

        for rule in payload.frequency:
            if rule.offset_minutes >= 0:
                raise HTTPException(
                    status_code=400,
                    detail="offset_minutes must be negative"
                )
    else:
        payload.frequency = None

    # =========================
    # Insert
    # =========================
    template_data = {
        "client_id": str(payload.client_id),
        "channel": payload.channel,
        "type": payload.type,
        "template_name": payload.template_name,
        "label": payload.label,
        "body": payload.body,
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
    Applies only to future appointments.
    """

    update_data = payload.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided to update"
        )

    # Validate frequency (DICT SAFE)
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
