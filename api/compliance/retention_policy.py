from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from api.config.config import supabase


RETENTION_APPLY_ENV = "EVOLVIAN_RETENTION_ALLOW_APPLY"


@dataclass(frozen=True)
class RetentionRule:
    table: str
    date_column: str
    retention_days: int
    action: str  # delete | anonymize
    description: str


def retention_rules_catalog() -> list[RetentionRule]:
    return [
        RetentionRule(
            table="history",
            date_column="created_at",
            retention_days=365,
            action="anonymize",
            description="Operational history kept for analytics/audit but message content is redacted.",
        ),
        RetentionRule(
            table="public_privacy_requests",
            date_column="created_at",
            retention_days=1095,
            action="delete",
            description="Privacy requests retained for 3 years then deleted.",
        ),
        RetentionRule(
            table="public_privacy_consents",
            date_column="created_at",
            retention_days=1095,
            action="delete",
            description="Public privacy consent logs retained for 3 years then deleted.",
        ),
        RetentionRule(
            table="widget_consents",
            date_column="consent_at",
            retention_days=1095,
            action="delete",
            description="Widget consent records retained for 3 years then deleted.",
        ),
        RetentionRule(
            table="appointment_usage",
            date_column="created_at",
            retention_days=730,
            action="delete",
            description="Appointment usage events retained for 2 years then deleted.",
        ),
        RetentionRule(
            table="appointment_reminders",
            date_column="created_at",
            retention_days=730,
            action="delete",
            description="Reminder execution metadata retained for 2 years then deleted.",
        ),
    ]


def get_rule_map() -> dict[str, RetentionRule]:
    return {rule.table: rule for rule in retention_rules_catalog()}


def normalize_table_selection(tables: list[str] | None) -> list[str]:
    rule_map = get_rule_map()
    if not tables:
        return list(rule_map.keys())
    normalized: list[str] = []
    for raw in tables:
        table = (raw or "").strip()
        if table and table in rule_map and table not in normalized:
            normalized.append(table)
    return normalized


def is_retention_apply_allowed() -> bool:
    return str(os.getenv(RETENTION_APPLY_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def compute_cutoff(now: datetime, retention_days: int) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc) - timedelta(days=max(1, retention_days))


def rule_to_dict(rule: RetentionRule, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    cutoff = compute_cutoff(current, rule.retention_days)
    payload = asdict(rule)
    payload["cutoff_at"] = cutoff.isoformat()
    return payload


def _fetch_candidate_ids(rule: RetentionRule, cutoff_iso: str, batch_size: int) -> list[str]:
    response = (
        supabase.table(rule.table)
        .select("id")
        .lt(rule.date_column, cutoff_iso)
        .limit(batch_size)
        .execute()
    )
    rows = response.data or []
    return [str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id") is not None]


def _apply_rule_batch(rule: RetentionRule, ids: list[str], *, run_at_iso: str) -> None:
    if not ids:
        return
    if rule.action == "delete":
        supabase.table(rule.table).delete().in_("id", ids).execute()
        return

    if rule.action == "anonymize":
        if rule.table == "history":
            supabase.table(rule.table).update(
                {
                    "content": "[redacted_by_retention_policy]",
                    "metadata": {
                        "redacted": True,
                        "redacted_at": run_at_iso,
                        "retention_policy": "v1",
                    },
                    "status": "retention_redacted",
                }
            ).in_("id", ids).execute()
            return
        # Fallback anonymization marker for other tables if enabled in future.
        supabase.table(rule.table).update(
            {
                "status": "retention_redacted",
            }
        ).in_("id", ids).execute()
        return

    raise ValueError(f"Unsupported retention action: {rule.action}")


def run_retention_job(
    *,
    apply: bool,
    tables: list[str] | None = None,
    batch_size: int = 500,
    max_batches: int = 20,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    rule_map = get_rule_map()
    selected_tables = normalize_table_selection(tables)

    if apply and not is_retention_apply_allowed():
        raise PermissionError(
            f"Retention apply blocked: set {RETENTION_APPLY_ENV}=true to enable destructive retention actions."
        )

    batch_size = max(1, min(batch_size, 1000))
    max_batches = max(1, min(max_batches, 200))

    results: list[dict[str, Any]] = []
    total_candidates = 0
    total_affected = 0
    run_at_iso = now.isoformat()

    for table in selected_tables:
        rule = rule_map.get(table)
        if not rule:
            continue

        cutoff = compute_cutoff(now, rule.retention_days).isoformat()
        table_candidates = 0
        table_affected = 0
        batches = 0
        capped = False
        errors: list[str] = []

        try:
            while batches < max_batches:
                ids = _fetch_candidate_ids(rule, cutoff, batch_size)
                if not ids:
                    break
                batches += 1
                table_candidates += len(ids)

                if apply:
                    _apply_rule_batch(rule, ids, run_at_iso=run_at_iso)
                    table_affected += len(ids)

            if batches >= max_batches:
                capped = True
        except Exception as error:  # noqa: BLE001
            errors.append(str(error))

        total_candidates += table_candidates
        total_affected += table_affected
        results.append(
            {
                "table": rule.table,
                "date_column": rule.date_column,
                "action": rule.action,
                "retention_days": rule.retention_days,
                "cutoff_at": cutoff,
                "batches_processed": batches,
                "candidate_rows": table_candidates,
                "affected_rows": table_affected,
                "capped": capped,
                "errors": errors,
            }
        )

    return {
        "apply": apply,
        "apply_allowed": is_retention_apply_allowed(),
        "batch_size": batch_size,
        "max_batches": max_batches,
        "tables": selected_tables,
        "results": results,
        "totals": {
            "candidate_rows": total_candidates,
            "affected_rows": total_affected,
        },
        "run_at": run_at_iso,
    }

