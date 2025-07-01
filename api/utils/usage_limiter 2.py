from datetime import datetime
from fastapi import HTTPException
from api.modules.assistant_rag.supabase_client import supabase

def check_and_increment_usage(client_id: str, usage_type: str):
    """
    Valida el uso contra el límite del plan y actualiza una fila única por cliente.
    usage_type: 'messages_used' o 'documents_uploaded'
    """
    try:
        # 1. Obtener plan actual del cliente usando join
        settings_res = supabase.table("client_settings")\
            .select("""
                client_id,
                plan_id,
                plans!plan_id(id, max_messages, max_documents, is_unlimited)
            """)\
            .eq("client_id", client_id)\
            .maybe_single()\
            .execute()

        if not settings_res or not settings_res.data:
            raise HTTPException(status_code=404, detail="Configuración de cliente no encontrada.")

        plan_data = settings_res.data.get("plans", {})

        if plan_data.get("is_unlimited"):
            return  # ✅ sin límite

        # 2. Determinar el límite
        if usage_type == "messages_used":
            limit = plan_data.get("max_messages", 0)
        elif usage_type == "documents_uploaded":
            limit = plan_data.get("max_documents", 0)
        else:
            raise HTTPException(status_code=400, detail="Tipo de uso inválido.")

        # 3. Obtener uso actual (y crear si no existe)
        usage_res = supabase.table("client_usage")\
            .select("messages_used, documents_uploaded")\
            .eq("client_id", client_id)\
            .maybe_single()\
            .execute()

        if not usage_res or not usage_res.data:
            # ⚠️ Crear fila si no existe
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": 0,
                "documents_uploaded": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            current_count = 0
        else:
            usage = usage_res.data
            current_count = usage.get(usage_type, 0)

        if current_count >= limit:
            raise HTTPException(
                status_code=403,
                detail="limit_reached"
            )

        # 4. Actualizar contador
        supabase.table("client_usage")\
            .update({
                usage_type: current_count + 1,
                "last_used_at": datetime.utcnow().isoformat()
            })\
            .eq("client_id", client_id)\
            .execute()

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en check_and_increment_usage: {e}")
        raise HTTPException(status_code=500, detail="Error al verificar uso del cliente.")
