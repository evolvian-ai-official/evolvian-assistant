from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.internal_auth import require_internal_request

router = APIRouter()

class ReminderPayload(BaseModel):
    client_id: str
    phone: str
    message: str

@router.post("/send_reminder")
async def send_whatsapp_reminder(payload: ReminderPayload, request: Request):
    require_internal_request(request)
    print("📨 Incoming WhatsApp reminder request:", payload)

    return {
        "status": "ok",
        "client_id": payload.client_id,
        "to": payload.phone,
        "message": payload.message
    }
