from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict
import uuid
import logging

from api.config.config import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================
# Payload
# =========================
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


# =========================
# Endpoint
# =========================
@router.post("/create_templates", tags=["Message Templates"])
def create_template(payload: CreateTemplatePayload):
    """
    Create message templates with support for multiple reminder rules.
    """

    # =========================
    # 1️⃣ Validaciones
    # =========================
    if payload.type == "appointment_reminder":
        if not payload.frequency or len(payload.frequency) == 0:
            raise HTTPException(
                status_code=400,
                detail="frequency is required for appointment_reminder templates"
            )

        # Validar offsets negativos
        for rule in payload.frequency:
            if rule.offset_minutes >= 0:
                raise HTTPException(
                    status_code=400,
                    detail="offset_minutes must be negative (minutes before appointment)"
                )
    else:
        # Para confirmation / cancellation no aplica frequency
        payload.frequency = None

    # =========================
    # 2️⃣ Insert template
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
        "is_active": payload.is_active
    }

    response = (
        supabase
        .table("message_templates")
        .insert(template_data)
        .execute()
    )

    if not response.data:
        logger.error("❌ Failed to create message template")
        raise HTTPException(
            status_code=500,
            detail="Failed to create message template"
        )

    return {
        "success": True,
        "template": response.data[0]
    }


    
