from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ReminderPayload(BaseModel):
    client_id: str
    phone: str
    message: str

@router.post("/send_reminder")
async def send_whatsapp_reminder(payload: ReminderPayload):
    print("📨 Incoming WhatsApp reminder request:", payload)

    return {
        "status": "ok",
        "client_id": payload.client_id,
        "to": payload.phone,
        "message": payload.message
    }
