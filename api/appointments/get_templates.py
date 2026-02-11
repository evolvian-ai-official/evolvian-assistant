from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import uuid

from api.config.config import supabase

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
# Response Model (FIX REAL)
# =========================
class MessageTemplateResponse(BaseModel):
    id: uuid.UUID
    channel: str
    type: str

    # ✅ WhatsApp = None, Email = string
    body: Optional[str] = None

    template_name: Optional[str] = None
    label: Optional[str] = None
    frequency: Optional[List[FrequencyRule]] = None

    # UI helper
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

    Used by:
    - Templates UI
    - Appointment creation
    """

    query = (
        supabase
        .table("message_templates")
        .select(
            "id, channel, type, body, frequency, template_name, label"
        )
        .eq("client_id", str(client_id))
        .eq("is_active", True)
    )

    if type:
        query = query.eq("type", type)

    res = query.order("template_name").execute()
    templates = res.data or []

    # UI helper flag
    for t in templates:
        t["is_meta_template"] = bool(t.get("template_name"))

    return templates
