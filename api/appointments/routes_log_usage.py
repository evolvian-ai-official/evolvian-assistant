from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
from api.internal_auth import has_valid_internal_token

router = APIRouter()

class MakeLogUsage(BaseModel):
    client_id: str
    appointment_id: str
    action: str
    channel: str = "whatsapp"

@router.post("/make_log_usage")   # 👈 FIX IMPOdRTANTÍSIMO
async def make_log_usage(data: MakeLogUsage, request: Request):

    try:
        if not has_valid_internal_token(request):
            authorize_client_request(request, data.client_id)

        result = supabase.table("appointment_usage").insert({
            "client_id": data.client_id,
            "appointment_id": data.appointment_id,
            "action": data.action,
            "channel": data.channel
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to log appointment usage")

        return {"logged": True}

    except HTTPException:
        raise
    except Exception as e:
        print("Error make_log_usage:", e)
        raise HTTPException(status_code=500, detail=str(e))
