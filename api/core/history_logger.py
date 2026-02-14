import logging
from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase

logger = logging.getLogger(__name__)


async def log_history(
    *,
    client_id: str,
    role: str,
    content: str,
    channel: str,
    source_type: str = "chat",
    provider: str = "internal",
    source_id: str | None = None,
    status: str = "sent",
    metadata: dict | None = None,
    session_id: str | None = None,
):
    """
    🔥 Evolvian Universal History Logger (Production Ready)

    - Guarda evento en tabla history
    - Incrementa usage diario mediante RPC
    - No rompe flujo principal
    - Compatible con multi-canal y multi-provider
    - Preparado para reminders, marketing y appointments
    """

    try:
        # ---------------------------------------------------------
        # 1️⃣ Insert en HISTORY
        # ---------------------------------------------------------
        history_payload = {
            "client_id": client_id,
            "role": role,
            "content": content,
            "channel": channel,
            "source_type": source_type,
            "provider": provider,
            "source_id": source_id,
            "status": status,
            "metadata": metadata,
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        supabase.table("history").insert(history_payload).execute()

        # ---------------------------------------------------------
        # 2️⃣ Incrementar usage diario (si existe función RPC)
        # ---------------------------------------------------------
        try:
            supabase.rpc("increment_usage", {
                "p_client_id": client_id,
                "p_channel": channel,
                "p_source_type": source_type
            }).execute()
        except Exception as usage_error:
            # No romper si falla usage
            logger.warning(f"⚠️ Usage increment failed: {usage_error}")

    except Exception as e:
        # Nunca romper flujo principal
        logger.error(f"❌ log_history failed: {str(e)}")
