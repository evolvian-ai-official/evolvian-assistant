import logging

from fastapi import HTTPException

from api.modules.assistant_rag.supabase_client import supabase
from api.utils.effective_plan import resolve_effective_plan_id


logger = logging.getLogger(__name__)


def get_client_plan_id(client_id: str) -> str:
    return resolve_effective_plan_id(client_id, supabase_client=supabase)


def client_has_active_feature(client_id: str, feature_key: str) -> bool:
    try:
        plan_id = get_client_plan_id(client_id)
        if not plan_id:
            return False

        res = (
            supabase.table("plan_features")
            .select("id")
            .eq("plan_id", plan_id)
            .eq("feature", str(feature_key or "").strip().lower())
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(res and getattr(res, "data", None))
    except Exception as e:
        logger.warning(
            "Could not verify feature access | client_id=%s | feature=%s | err=%s",
            client_id,
            feature_key,
            e,
        )
        return False


def require_client_feature(client_id: str, feature_key: str, *, required_plan_label: str = "premium") -> None:
    if client_has_active_feature(client_id, feature_key):
        return

    plan_id = get_client_plan_id(client_id)
    raise HTTPException(
        status_code=403,
        detail=(
            f"Feature '{str(feature_key or '').strip().lower()}' requires the "
            f"{str(required_plan_label or 'premium').strip().lower()} plan "
            f"(current plan: {plan_id or 'free'})."
        ),
    )
