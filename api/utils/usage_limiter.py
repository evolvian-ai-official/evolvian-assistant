# api/modules/usage_limiter.py

from datetime import datetime
from fastapi import HTTPException
from api.modules.assistant_rag.supabase_client import supabase
from api.utils.effective_plan import normalize_plan_id, resolve_effective_plan_id

def check_and_increment_usage(client_id: str, usage_type: str, delta: int = 1):
    """
    Valida el uso contra el límite del plan y actualiza los contadores
    en la tabla client_usage.
    usage_type: 'messages_used' o 'documents_uploaded'
    delta: número a sumar o restar (por ejemplo +1 al subir, -1 al borrar).
    """
    try:
        # 1. Obtener plan actual
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

        base_plan_id = normalize_plan_id(settings_res.data.get("plan_id"))
        effective_plan_id = resolve_effective_plan_id(
            client_id,
            base_plan_id=base_plan_id,
            supabase_client=supabase,
        )
        plan_data = settings_res.data.get("plans", {}) or {}

        if effective_plan_id != base_plan_id:
            override_plan_res = (
                supabase.table("plans")
                .select("id, max_messages, max_documents, is_unlimited")
                .eq("id", effective_plan_id)
                .maybe_single()
                .execute()
            )
            if override_plan_res and override_plan_res.data:
                plan_data = override_plan_res.data

        if plan_data.get("is_unlimited"):
            return  # ✅ sin límite

        # 2. Determinar límite según tipo
        if usage_type == "messages_used":
            limit = plan_data.get("max_messages", 0)
        elif usage_type == "documents_uploaded":
            limit = plan_data.get("max_documents", 0)
        else:
            raise HTTPException(status_code=400, detail="Tipo de uso inválido.")

        # 3. Obtener uso actual (crear fila si no existe)
        usage_res = supabase.table("client_usage")\
            .select("messages_used, documents_uploaded")\
            .eq("client_id", client_id)\
            .limit(1)\
            .execute()

        if not usage_res or not usage_res.data:
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": 0,
                "documents_uploaded": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            current_count = 0
        else:
            usage = usage_res.data[0]
            current_count = usage.get(usage_type, 0) or 0

        # 4. Calcular nuevo valor
        new_count = current_count + delta

        if new_count < 0:
            new_count = 0

        if delta > 0 and new_count > limit:
            raise HTTPException(status_code=403, detail="limit_reached")

        # 5. Actualizar contador
        supabase.table("client_usage")\
            .update({
                usage_type: new_count,
                "last_used_at": datetime.utcnow().isoformat()
            })\
            .eq("client_id", client_id)\
            .execute()

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en check_and_increment_usage: {e}")
        raise HTTPException(status_code=500, detail="Error al verificar uso del cliente.")


def sync_documents_usage(client_id: str):
    """
    Sincroniza documents_uploaded en client_usage con la cantidad
    real de archivos en el bucket evolvian-documents.
    """
    try:
        files = supabase.storage.from_("evolvian-documents").list(path=client_id)

        total_files = 0
        for f in files:
            if f["id"].endswith("/"):  # 📁 subcarpeta
                subfiles = supabase.storage.from_("evolvian-documents").list(path=f["name"])
                total_files += len(subfiles)
            else:
                total_files += 1

        supabase.table("client_usage").update({
            "documents_uploaded": total_files,
            "last_used_at": datetime.utcnow().isoformat()
        }).eq("client_id", client_id).execute()

        print(f"✅ Sincronizado client {client_id}: {total_files} documentos")
        return total_files

    except Exception as e:
        print(f"❌ Error en sync_documents_usage: {e}")
        raise HTTPException(status_code=500, detail="Error al sincronizar documentos del cliente.")
