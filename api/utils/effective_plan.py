import logging
from typing import Any

from api.config.config import supabase


logger = logging.getLogger(__name__)

ALLOWED_OVERRIDE_PLANS = {"free", "starter", "premium", "white_label", "enterprise"}


def normalize_plan_id(plan_id: str | None) -> str:
    normalized = str(plan_id or "").strip().lower()
    if normalized == "enterprise":
        return "white_label"
    return normalized


def get_client_override_plan_id(client_id: str, *, supabase_client: Any = None) -> str | None:
    if not client_id:
        return None

    client = supabase_client or supabase
    try:
        res = (
            client.table("clients")
            .select("override_plan")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        raw_override = (res.data or {}).get("override_plan") if res else None
        if not raw_override:
            return None

        normalized_raw = str(raw_override).strip().lower()
        if normalized_raw not in ALLOWED_OVERRIDE_PLANS:
            logger.warning(
                "Ignoring invalid override_plan for client_id=%s: %s",
                client_id,
                raw_override,
            )
            return None
        return normalize_plan_id(normalized_raw)
    except Exception as exc:
        logger.warning("Could not resolve override_plan for client %s: %s", client_id, exc)
        return None


def resolve_effective_plan_id(
    client_id: str,
    *,
    base_plan_id: str | None = None,
    supabase_client: Any = None,
) -> str:
    client = supabase_client or supabase

    override_plan_id = get_client_override_plan_id(client_id, supabase_client=client)
    if override_plan_id:
        return override_plan_id

    normalized_base = normalize_plan_id(base_plan_id)
    if normalized_base:
        return normalized_base

    try:
        res = (
            client.table("client_settings")
            .select("plan_id")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        return normalize_plan_id((res.data or {}).get("plan_id")) or "free"
    except Exception as exc:
        logger.warning("Could not resolve base plan_id for client %s: %s", client_id, exc)
        return "free"
