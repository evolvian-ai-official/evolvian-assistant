# src/api/dashboard_summary.py

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
import os
import logging

router = APIRouter()

@router.get("/dashboard_summary")
def dashboard_summary(client_id: str = Query(...)):
    try:
        logging.info(f"📊 Obteniendo dashboard_summary para client_id={client_id}")

        # 1. Configuración del asistente y su plan (join con plans + features)
        settings_res = supabase.table("client_settings")\
            .select("assistant_name, language, temperature, plan_id, show_powered_by, plans!client_settings_plan_id_fkey(*, plan_features(*))")\
            .eq("client_id", client_id)\
            .single()\
            .execute()

        if not settings_res.data:
            raise HTTPException(status_code=404, detail="client_id no encontrado")

        config = settings_res.data
        plan = config.get("plans", {})

        plan_info = {
            "id": plan.get("id"),
            "name": plan.get("name"),
            "max_messages": plan.get("max_messages"),
            "max_documents": plan.get("max_documents"),
            "is_unlimited": plan.get("is_unlimited"),
            "show_powered_by": plan.get("show_powered_by"),
            "supports_chat": plan.get("supports_chat"),
            "supports_email": plan.get("supports_email"),
            "supports_whatsapp": plan.get("supports_whatsapp"),
            "price_usd": plan.get("price_usd"),
            "plan_features": [f["feature"] for f in plan.get("plan_features", [])]
        }

        # 2. Uso actual (adaptado al modelo por tipo)
        usage_raw = supabase.table("client_usage")\
            .select("type, value, last_used_at")\
            .eq("client_id", client_id)\
            .eq("channel", "chat")\
            .execute()

        usage = {
            "messages_used": 0,
            "documents_uploaded": 0,
            "last_used_at": None
        }

        if usage_raw.data:
            for row in usage_raw.data:
                if row["type"] == "question":
                    usage["messages_used"] = row["value"]
                    usage["last_used_at"] = row["last_used_at"]
                elif row["type"] == "document":
                    usage["documents_uploaded"] = row["value"]

        # 3. Canales activos
        channels_res = supabase.table("channels")\
            .select("type")\
            .eq("client_id", client_id)\
            .execute()

        active_channels = [c["type"] for c in channels_res.data]
        all_channels = ["chat", "whatsapp", "email"]
        channels = {c: c in active_channels for c in all_channels}

        # 4. Últimas 3 preguntas del historial
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

        # 5. Últimos 2 documentos subidos (desde filesystem)
        docs_path = f"data/{client_id}"
        try:
            filenames = sorted(
                [{"file_name": f, "uploaded_at": None} for f in os.listdir(docs_path)],
                key=lambda x: x["file_name"]
            )[:2]
        except FileNotFoundError:
            filenames = []

        return JSONResponse(content={
            "plan": plan_info,
            "usage": usage,
            "channels": channels,
            "assistant_config": {
                "assistant_name": config.get("assistant_name", "Evolvian"),
                "language": config.get("language", "es"),
                "temperature": config.get("temperature", 0.7),
                "show_powered_by": config.get("show_powered_by", True)
            },
            "history_preview": history_preview,
            "documents_preview": filenames
        })

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error en /dashboard_summary")
        raise HTTPException(status_code=500, detail="Error al obtener el resumen del cliente.")
