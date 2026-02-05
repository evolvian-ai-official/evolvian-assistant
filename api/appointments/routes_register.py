from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from datetime import datetime

router = APIRouter() #d

class MakeRegisterAppointment(BaseModel):
    client_id: str
    user_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None
    scheduled_time: datetime
    appointment_type: str | None = None
    calendar_event_id: str | None = None

@router.post("/make_register")
async def make_register_appointment(data: MakeRegisterAppointment):

    try:
        result = supabase.table("appointments").insert({
            "client_id": data.client_id,
            "user_name": data.user_name,
            "user_email": data.user_email,
            "user_phone": data.user_phone,
            "scheduled_time": data.scheduled_time.isoformat(),
            "appointment_type": data.appointment_type,
            "calendar_event_id": data.calendar_event_id,
            "status": "pending_confirmation"
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create appointment")

        return {
            "appointment_id": result.data[0]["id"],
            "status": "created"
        }

    except Exception as e:
        print("Error make_register:", e)
        raise HTTPException(status_code=500, detail=str(e))
