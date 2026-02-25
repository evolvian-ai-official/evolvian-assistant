from __future__ import annotations

import logging
from typing import Any, Optional

from api.config.config import supabase

logger = logging.getLogger(__name__)

LANGUAGE_FAMILY_DEFAULT_LOCALE = {
    "es": "es_MX",
    "en": "en_US",
}


def normalize_language_family(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw.startswith("es"):
        return "es"
    if raw.startswith("en"):
        return "en"
    if raw in {"spanish", "espanol", "español"}:
        return "es"
    if raw == "english":
        return "en"
    return None


def normalize_locale_code(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip().replace("-", "_")
    if not raw:
        return None
    parts = [p for p in raw.split("_") if p]
    if not parts:
        return None
    language = normalize_language_family(parts[0])
    if not language:
        return None
    if len(parts) >= 2:
        return f"{language}_{parts[1].upper()}"
    return LANGUAGE_FAMILY_DEFAULT_LOCALE.get(language, raw)


def language_family_from_locale(locale_code: Optional[str]) -> Optional[str]:
    normalized_locale = normalize_locale_code(locale_code)
    if not normalized_locale:
        return None
    return normalize_language_family(normalized_locale.split("_", 1)[0])


def normalize_language_preferences(
    *,
    language_family: Optional[str] = None,
    locale_code: Optional[str] = None,
    fallback_language: str = "es",
) -> tuple[str, str]:
    locale = normalize_locale_code(locale_code)
    family = normalize_language_family(language_family)

    if locale and not family:
        family = language_family_from_locale(locale)
    if family and not locale:
        locale = LANGUAGE_FAMILY_DEFAULT_LOCALE.get(family, "es_MX")

    if not family:
        family = normalize_language_family(fallback_language) or "es"
    if not locale:
        locale = LANGUAGE_FAMILY_DEFAULT_LOCALE.get(family, "es_MX")
    return family, locale


def get_client_default_language_preferences(client_id: Optional[str]) -> tuple[str, str]:
    if not client_id:
        return ("es", "es_MX")
    try:
        response = (
            supabase.table("client_settings")
            .select("appointments_template_language")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [{}])[0]
        client_lang = row.get("appointments_template_language") or "es"
    except Exception as exc:
        logger.warning(
            "⚠️ Failed loading client_settings template language for template resolution | client_id=%s | error=%s",
            client_id,
            exc,
        )
        client_lang = "es"
    return normalize_language_preferences(language_family=client_lang)


def resolve_appointment_language_preferences(client_id: str, appointment: Optional[dict]) -> tuple[str, str]:
    appointment = appointment or {}
    return normalize_language_preferences(
        language_family=appointment.get("recipient_language"),
        locale_code=appointment.get("recipient_locale"),
        fallback_language=get_client_default_language_preferences(client_id)[0],
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _safe_select_templates_with_language(client_id: str, channel: str, template_type: str):
    try:
        return (
            supabase
            .table("message_templates")
            .select(
                """
                id,
                client_id,
                channel,
                type,
                body,
                is_active,
                frequency,
                created_at,
                updated_at,
                template_name,
                label,
                meta_template_id,
                language_family,
                locale_code,
                variant_key,
                priority,
                is_default_for_language,
                meta_approved_templates (
                    template_name,
                    parameter_count,
                    language,
                    preview_body,
                    is_active
                )
                """
            )
            .eq("client_id", client_id)
            .eq("channel", channel)
            .eq("type", template_type)
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception as exc:
        # Backwards-compatible fallback before DB migration is applied.
        logger.warning(
            "⚠️ message_templates language columns unavailable (fallback query) | client_id=%s | channel=%s | type=%s | error=%s",
            client_id,
            channel,
            template_type,
            exc,
        )
        return (
            supabase
            .table("message_templates")
            .select(
                """
                id,
                client_id,
                channel,
                type,
                body,
                is_active,
                frequency,
                created_at,
                updated_at,
                template_name,
                label,
                meta_template_id,
                meta_approved_templates (
                    template_name,
                    parameter_count,
                    language,
                    preview_body,
                    is_active
                )
                """
            )
            .eq("client_id", client_id)
            .eq("channel", channel)
            .eq("type", template_type)
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .execute()
        )


def enrich_template_language_fields(row: dict) -> dict:
    template = dict(row or {})
    meta = template.get("meta_approved_templates") if isinstance(template.get("meta_approved_templates"), dict) else None
    is_whatsapp = str(template.get("channel") or "").lower() == "whatsapp"

    if is_whatsapp and meta:
        family, locale = normalize_language_preferences(locale_code=meta.get("language"))
    else:
        family, locale = normalize_language_preferences(
            language_family=template.get("language_family"),
            locale_code=template.get("locale_code"),
        )

    template["_resolved_language_family"] = family
    template["_resolved_locale_code"] = locale
    template["_resolved_meta"] = meta
    return template


def choose_best_template_for_language(
    templates: list[dict],
    *,
    target_language_family: str,
    target_locale_code: str,
    require_frequency: bool = False,
    require_body: bool = False,
    allow_whatsapp_legacy: bool = False,
) -> Optional[dict]:
    candidates: list[dict] = []
    for row in templates or []:
        if not isinstance(row, dict):
            continue
        enriched = enrich_template_language_fields(row)
        channel = str(enriched.get("channel") or "").lower()
        if require_frequency and not enriched.get("frequency"):
            continue
        if require_body and channel in {"email", "widget"} and not str(enriched.get("body") or "").strip():
            continue
        if channel == "whatsapp":
            if not enriched.get("meta_template_id"):
                if not allow_whatsapp_legacy:
                    continue
            if enriched.get("_resolved_meta") is None:
                # Skip broken/missing canonical metadata; sender depends on it.
                continue
        candidates.append(enriched)

    if not candidates:
        return None

    def _score(row: dict) -> tuple[int, int, int, int, str]:
        row_locale = row.get("_resolved_locale_code")
        row_family = row.get("_resolved_language_family")
        exact_locale = 1 if row_locale == target_locale_code else 0
        same_family = 1 if row_family == target_language_family else 0
        default_for_lang = 1 if _safe_bool(row.get("is_default_for_language")) and same_family else 0
        priority = _safe_int(row.get("priority"), 0)
        updated_at = str(row.get("updated_at") or row.get("created_at") or "")
        return (exact_locale, same_family, default_for_lang, priority, updated_at)

    candidates.sort(key=_score, reverse=True)
    return candidates[0]


def resolve_template_for_appointment(
    *,
    client_id: str,
    channel: str,
    template_type: str,
    appointment: Optional[dict] = None,
    require_frequency: bool = False,
    require_body: bool = False,
) -> Optional[dict]:
    target_language, target_locale = resolve_appointment_language_preferences(client_id, appointment)
    response = _safe_select_templates_with_language(client_id, channel, template_type)
    rows = response.data if hasattr(response, "data") else []
    return choose_best_template_for_language(
        rows or [],
        target_language_family=target_language,
        target_locale_code=target_locale,
        require_frequency=require_frequency,
        require_body=require_body,
    )


def resolve_locale_for_rendering(
    *,
    client_id: str,
    appointment: Optional[dict],
    template_row: Optional[dict] = None,
    meta_row: Optional[dict] = None,
) -> tuple[str, str]:
    if meta_row:
        return normalize_language_preferences(locale_code=meta_row.get("language"))

    if template_row:
        row = dict(template_row)
        if meta_row is None and isinstance(row.get("meta_approved_templates"), dict):
            return normalize_language_preferences(locale_code=row["meta_approved_templates"].get("language"))
        family = row.get("language_family")
        locale = row.get("locale_code")
        if family or locale:
            return normalize_language_preferences(language_family=family, locale_code=locale)

    return resolve_appointment_language_preferences(client_id, appointment)
