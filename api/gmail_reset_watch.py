from fastapi import APIRouter, HTTPException
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service

router = APIRouter(prefix="/gmail_reset_watch", tags=["Maintenance"])

@router.post("")
async def reset_gmail_watch(client_id: str):
    """
    🔄 Reinicia el canal de notificaciones Gmail Pub/Sub para un cliente.
    Evita que se reprocesen correos antiguos.
    """
    try:
        # Buscar canal Gmail activo
        channel_resp = (
            supabase.table("channels")
            .select("*")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", "gmail")
            .eq("active", True)
            .maybe_single()
            .execute()
        )
        if not channel_resp or not channel_resp.data:
            raise HTTPException(status_code=404, detail="Canal Gmail no encontrado")

        channel = channel_resp.data
        service = get_gmail_service(channel)
        email = channel["value"]

        # 🔴 Detener el canal actual
        service.users().stop(userId="me").execute()
        print(f"🛑 Canal Pub/Sub detenido para {email}")

        # 🟢 Iniciar nuevo canal watch
        result = service.users().watch(
            userId="me",
            body={
                "labelIds": ["INBOX"],
                "topicName": "projects/evolvian-ai-auth/topics/gmail-notifications"
            }
        ).execute()

        print(f"✅ Canal Pub/Sub reiniciado para {email}")
        print(f"🧩 Nuevo historyId: {result.get('historyId')}")

        # Guardar nuevo historyId en tabla
        supabase.table("gmail_sync_state").upsert({
            "email": email,
            "last_history_id": result.get("historyId")
        }).execute()

        return {
            "status": "ok",
            "message": f"Canal Gmail reiniciado para {email}",
            "new_history_id": result.get("historyId")
        }

    except Exception as e:
        print(f"🔥 Error reiniciando canal Gmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))
