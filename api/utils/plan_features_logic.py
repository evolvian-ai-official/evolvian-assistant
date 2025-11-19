# ============================================================
# ✅ plan_features_logic.py — Control centralizado de features por plan
# ============================================================
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_client_plan_id(client_id: str) -> str | None:
    """Retorna el plan_id asociado al cliente"""
    try:
        res = (
            supabase.table("client_settings")
            .select("plan_id")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        if res and res.data:
            return res.data["plan_id"]
    except Exception as e:
        print(f"⚠️ Error getting plan_id for client {client_id}: {e}")
    return None


def client_has_feature(client_id: str, feature_key: str) -> bool:
    """
    Verifica si el cliente tiene acceso al feature_key definido en plan_features.
    Ejemplo: feature_key = 'calendar_sync'
    """
    try:
        plan_id = get_client_plan_id(client_id)
        if not plan_id:
            return False

        res = (
            supabase.table("plan_features")
            .select("feature")
            .eq("plan_id", plan_id)
            .execute()
        )

        if not res or not res.data:
            return False

        features = [f["feature"].lower() for f in res.data]
        return feature_key.lower() in features

    except Exception as e:
        print(f"⚠️ Error verifying feature {feature_key} for {client_id}: {e}")
        return False
