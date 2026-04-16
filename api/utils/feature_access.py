import logging

from fastapi import HTTPException

from api.modules.assistant_rag.supabase_client import supabase
from api.utils.effective_plan import resolve_effective_plan_id


logger = logging.getLogger(__name__)


def _normalize_feature_keys(*feature_keys: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for key in feature_keys:
        value = str(key or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


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


def client_has_all_active_features(client_id: str, *feature_keys: str) -> bool:
    normalized_keys = _normalize_feature_keys(*feature_keys)
    if not normalized_keys:
        return True

    try:
        plan_id = get_client_plan_id(client_id)
        if not plan_id:
            return False

        res = (
            supabase.table("plan_features")
            .select("feature")
            .eq("plan_id", plan_id)
            .eq("is_active", True)
            .in_("feature", normalized_keys)
            .execute()
        )
        active_features = {
            str(row.get("feature") or "").strip().lower()
            for row in (getattr(res, "data", None) or [])
        }
        return set(normalized_keys).issubset(active_features)
    except Exception as e:
        logger.warning(
            "Could not verify multi-feature access | client_id=%s | features=%s | err=%s",
            client_id,
            normalized_keys,
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
