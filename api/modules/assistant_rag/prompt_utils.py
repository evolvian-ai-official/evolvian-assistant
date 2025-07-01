# api/modules/assistant_rag/prompt_utils.py

from api.modules.assistant_rag.supabase_client import supabase

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

def get_prompt_for_client(client_id: str) -> str:
    try:
        res = supabase.table("client_settings").select("custom_prompt").eq("client_id", client_id).single().execute()
        return res.data.get("custom_prompt") or DEFAULT_PROMPT
    except Exception as e:
        print(f"⚠️ Error obteniendo prompt personalizado: {e}")
        return DEFAULT_PROMPT
