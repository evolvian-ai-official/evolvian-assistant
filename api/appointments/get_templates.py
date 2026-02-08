from fastapi import APIRouter, Depends, HTTPException
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
# Payload (Query Params)
# =========================
class GetMessageTemplatesPayload(BaseModel):
    client_id: uuid.UUID
    type: str  # e.g. "appointment_reminder"


# =========================
# Frequency Model (JSON ARRAY)
# =========================
class FrequencyOffset(BaseModel):
    unit: str   # "minutes", "hours", "days"
    value: int  # e.g. 1


# =========================
# Response Model
# =========================
class MessageTemplateResponse(BaseModel):
    id: uuid.UUID
    channel: str
    frequency: Optional[List[FrequencyOffset]]
    template_name: str
    label: str


# =========================
# Endpoint
# =========================
@router.get(
    "",
    response_model=List[MessageTemplateResponse]
)
def get_message_templates(
    payload: GetMessageTemplatesPayload = Depends(),
):
    """
    Returns active message templates for a client.

    Used by Create Appointment modal (UI).
    """

    # 🧠 Validación mínima
    if not payload.client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id is required"
        )

    # 🔎 Query Supabase
    res = (
        supabase
        .table("message_templates")
        .select("id, channel, frequency, template_name, label")
        .eq("client_id", str(payload.client_id))
        .eq("type", payload.type)
        .eq("is_active", True)
        .order("template_name")
        .execute()
    )

    if not res.data:
        return []

    # ✅ Retorno alineado con DB (frequency = array)
    return [
        MessageTemplateResponse(
            id=row["id"],
            channel=row["channel"],
            frequency=row.get("frequency"),
            template_name=row["template_name"],
            label=row["label"],
        )
        for row in res.data
    ]
