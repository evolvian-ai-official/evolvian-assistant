from fastapi import APIRouter, HTTPException, Query
from api.modules.assistant_rag.supabase_client import get_client_whatsapp_config

router = APIRouter()

@router.get("/get_whatsapp_config")
async def get_whatsapp_config(client_id: str = Query(..., description="Client ID to retrieve WhatsApp config")):
    try:
        config = await get_client_whatsapp_config(client_id)
        if not config:
            raise HTTPException(status_code=404, detail="No WhatsApp configuration found for this client.")
        return config
    except Exception as e:
        print("❌ Error in /get_whatsapp_config:", e)
        raise HTTPException(status_code=500, detail="Internal server error.")
