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
    tags=["Appointments"]
)

# =========================
# Frequency Model (DB aligned)
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
    template_name: str
    label: Optional[str]
    frequency: Optional[List[FrequencyRule]] = None

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
    - Templates UI (ALL templates)
    - Create Appointment modal (filtered by type)
    """

    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    query = (
        supabase
        .table("message_templates")
        .select("id, channel, frequency, template_name, label")
        .eq("client_id", str(client_id))
        .eq("is_active", True)
    )

    # ✅ Filtrar solo si viene type
    if type:
        query = query.eq("type", type)

    res = query.order("template_name").execute()

    return res.data or []
