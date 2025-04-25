# api/dashboard_summary.py

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from modules.assistant_rag.supabase_client import supabase
import os

router = APIRouter()

@router.get("/dashboard_summary")
def dashboard_summary(client_id: str = Query(...)):
    try:
        # 1. Configuración del asistente y plan
        settings_res = supabase.table("client_settings")\
            .select("assistant_name, language, temperature, plan")\
            .eq("client_id", client_id)\
            .single()\
            .execute()

        if not settings_res.data:
            raise HTTPException(status_code=404, detail="client_id no encontrado")

        config = settings_res.data
        plan_id = config["plan"]

        # 2. Obtener el plan y sus features relacionados
        plan_res = supabase.table("plans")\
            .select("id, name, max_messages, max_documents, is_unlimited, show_powered_by, supports_chat, supports_email, supports_whatsapp, price_usd, plan_features(feature)")\
            .eq("id", plan_id)\
            .single()\
            .execute()

        # 3. Uso actual
        usage_res = supabase.table("client_usage")\
            .select("messages_used, documents_uploaded, last_used_at")\
            .eq("client_id", client_id)\
            .limit(1)\
            .execute()
        
        usage = usage_res.data[0] if usage_res.data else {
            "messages_used": 0,
            "documents_uploaded": 0,
            "last_used_at": None
        }

        # 4. Canales activos
        channels_res = supabase.table("channels")\
            .select("type")\
            .eq("client_id", client_id)\
            .execute()
        
        active_channels = [c["type"] for c in channels_res.data]
        all_channels = ["chat", "whatsapp", "email"]
        channels = {c: c in active_channels for c in all_channels}

        # 5. Últimas 3 preguntas del historial
        history_res = supabase.table("history")\
            .select("question, created_at, channel")\
            .eq("client_id", client_id)\
            .order("created_at", desc=True)\
            .limit(3)\
            .execute()
        
        history_preview = [{
            "timestamp": h["created_at"],
            "channel": h["channel"],
            "question": h["question"][:120]
        } for h in history_res.data]

        # 6. Últimos 2 documentos subidos (desde filesystem)
        docs_path = f"data/{client_id}"
        try:
            filenames = sorted(
                [{"filename": f, "uploaded_at": None} for f in os.listdir(docs_path)],
                key=lambda x: x["filename"]
            )[:2]
        except FileNotFoundError:
            filenames = []

        return JSONResponse(content={
            "plan": plan_res.data,
            "usage": usage,
            "channels": channels,
            "assistant_config": {
                "assistant_name": config["assistant_name"],
                "language": config["language"],
                "temperature": config["temperature"]
            },
            "history_preview": history_preview,
            "documents_preview": filenames
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en /dashboard_summary: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener el resumen del cliente.")
