from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
import logging
from datetime import datetime

router = APIRouter()


def format_date(dt_str):
    """Convierte un string ISO en un formato legible: Sep 24, 2025"""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return dt_str


def count_bucket_documents(client_id: str) -> int:
    """Cuenta los archivos en el bucket evolvian-documents."""
    try:
        total_files = 0
        root_files = supabase.storage.from_("evolvian-documents").list(path=client_id)
        for f in root_files:
            if f["id"].endswith("/"):  # 📁 subcarpeta
                subfiles = supabase.storage.from_("evolvian-documents").list(path=f["name"])
                total_files += len(subfiles)
            else:
                total_files += 1
        return total_files
    except Exception as e:
        logging.error(f"❌ Error contando documentos en bucket: {e}")
        return 0


@router.get("/dashboard_summary")
def dashboard_summary(client_id: str = Query(...)):
    try:
        logging.info(f"📊 Obteniendo dashboard_summary para client_id={client_id}")

        # 1️⃣ Configuración del asistente y plan
        settings_res = (
            supabase.table("client_settings")
            .select(
                "assistant_name, language, temperature, plan_id, show_powered_by, "
                "subscription_start, subscription_end, "
                "plans!client_settings_plan_id_fkey("
                "id, name, max_messages, max_documents, is_unlimited, "
                "show_powered_by, supports_chat, supports_email, supports_whatsapp, price_usd, "
                "plan_features(feature)"
                ")"
            )
            .eq("client_id", client_id)
            .single()
            .execute()
        )

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
            "plan_features": [f["feature"] for f in plan.get("plan_features", [])],
        }

        subscription_start = config.get("subscription_start")
        subscription_end = config.get("subscription_end")

        # 2️⃣ Contar mensajes del usuario (role=user)
        msg_count_res = (
            supabase.table("history")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("role", "user")
            .execute()
        )

        total_user_messages = getattr(msg_count_res, "count", 0) or 0
        logging.info(f"💬 Mensajes de usuario encontrados: {total_user_messages}")

        # 3️⃣ Uso actual (sincronizado con client_usage)
        usage_row = (
            supabase.table("client_usage")
            .select("messages_used, documents_uploaded, last_used_at, created_at")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        usage = {
            "messages_used": total_user_messages,
            "documents_uploaded": 0,
            "last_used_at": datetime.utcnow().isoformat(),
        }

        if usage_row.data:
            supabase.table("client_usage").update({
                "messages_used": total_user_messages,
                "last_used_at": usage["last_used_at"],
            }).eq("client_id", client_id).execute()
        else:
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": total_user_messages,
                "documents_uploaded": 0,
                "last_used_at": usage["last_used_at"],
            }).execute()

        # 4️⃣ Sincronizar número de documentos
        bucket_count = count_bucket_documents(client_id)
        usage["documents_uploaded"] = bucket_count
        supabase.table("client_usage").update({
            "documents_uploaded": bucket_count,
        }).eq("client_id", client_id).execute()

        # 5️⃣ Canales activos
        channels_res = supabase.table("channels").select("type").eq("client_id", client_id).execute()
        active_channels = [c["type"] for c in channels_res.data or []]
        all_channels = ["chat", "whatsapp", "email"]
        channels = {c: c in active_channels for c in all_channels}

        # 6️⃣ Historial (últimos 3 mensajes reales del usuario)
        history_res = (
            supabase.table("history")
            .select("content, created_at, channel, role")
            .eq("client_id", client_id)
            .eq("role", "user")  # ✅ ya solo usamos user/assistant
            .not_.is_("content", None)
            .neq("content", "")
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )

        history_preview = []
        if history_res.data:
            for h in history_res.data:
                if not h or not isinstance(h, dict):
                    continue

                content = h.get("content")
                # ✅ si content es JSON, extrae texto
                if isinstance(content, dict):
                    content = content.get("text") or str(content)
                if not content or not str(content).strip():
                    continue

                history_preview.append({
                    "timestamp": h.get("created_at"),
                    "channel": h.get("channel", "chat"),
                    "question": str(content).strip()[:120],
                })

        # 7️⃣ Sugerencia de upgrade
        upgrade_suggestion = None
        if not plan_info["is_unlimited"] and plan_info["max_messages"]:
            percent = (usage["messages_used"] / plan_info["max_messages"]) * 100
            if percent >= 80:
                if plan_info["id"] == "free":
                    upgrade_suggestion = {"action": "upgrade", "to": "starter"}
                elif plan_info["id"] == "starter":
                    upgrade_suggestion = {"action": "upgrade", "to": "premium"}
                elif plan_info["id"] == "premium":
                    upgrade_suggestion = {"action": "contact_support", "email": "support@evolvianai.com"}

        # ✅ Respuesta final
        return JSONResponse(
            content={
                "plan": plan_info,
                "usage": usage,
                "channels": channels,
                "assistant_config": {
                    "assistant_name": config.get("assistant_name", "Evolvian"),
                    "language": config.get("language", "es"),
                    "temperature": config.get("temperature", 0.7),
                    "show_powered_by": config.get("show_powered_by", True),
                },
                "history_preview": history_preview,
                "upgrade_suggestion": upgrade_suggestion,
                "subscription_start": format_date(subscription_start),
                "subscription_end": format_date(subscription_end),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Error en /dashboard_summary")
        raise HTTPException(status_code=500, detail="Error al obtener el resumen del cliente.")
