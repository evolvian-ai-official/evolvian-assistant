from datetime import datetime
from fastapi import HTTPException
from modules.assistant_rag.supabase_client import supabase

def check_and_increment_usage(client_id: str, usage_type: str):
    """
    Valida el uso contra el límite del plan y actualiza una fila única por cliente.
    usage_type: 'messages_used' o 'documents_uploaded'
    """
    try:
        # 1. Obtener plan actual
        settings_res = supabase.table("client_settings")\
            .select("plan")\
            .eq("client_id", client_id)\
            .limit(1)\
            .execute()

        plan_id = settings_res.data[0]["plan"] if settings_res.data else "free"

        # 2. Obtener límites del plan
        plan_res = supabase.table("plans")\
            .select("max_messages, max_documents, is_unlimited")\
            .eq("id", plan_id)\
            .single()\
            .execute()

        if not plan_res.data:
            raise HTTPException(status_code=500, detail="Plan del cliente no válido.")

        if plan_res.data.get("is_unlimited"):
            return  # ✅ sin límite

        # 3. Determinar el límite
        if usage_type == "messages_used":
            limit = plan_res.data.get("max_messages")
        elif usage_type == "documents_uploaded":
            limit = plan_res.data.get("max_documents")
        else:
            raise HTTPException(status_code=400, detail="Tipo de uso inválido.")

        # 4. Obtener uso actual (y crear si no existe)
        usage_res = supabase.table("client_usage")\
            .select("messages_used, documents_uploaded")\
            .eq("client_id", client_id)\
            .limit(1)\
            .execute()

        if not usage_res.data:
            # ⚠️ Crear fila si no existe
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": 0,
                "documents_uploaded": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            current_count = 0
        else:
            usage = usage_res.data[0]
            current_count = usage.get(usage_type, 0)

        if current_count >= limit:
            raise HTTPException(
                status_code=403,
                detail="Límite alcanzado para tu plan actual. Por favor, actualiza tu plan para continuar."
            )

        # 5. Actualizar contador
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
