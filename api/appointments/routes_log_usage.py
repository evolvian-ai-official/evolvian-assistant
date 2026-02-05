from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

class MakeLogUsage(BaseModel):
    client_id: str
    appointment_id: str
    action: str
    channel: str = "whatsapp"

@router.post("/make_log_usage")   # 👈 FIX IMPOdRTANTÍSIMO
async def make_log_usage(data: MakeLogUsage):

    try:
        result = supabase.table("appointment_usage").insert({
            "client_id": data.client_id,
            "appointment_id": data.appointment_id,
            "action": data.action,
            "channel": data.channel
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to log appointment usage")

        return {"logged": True}

    except Exception as e:
        print("Error make_log_usage:", e)
        raise HTTPException(status_code=500, detail=str(e))
