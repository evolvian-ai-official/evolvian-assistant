from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.config.config import supabase
from api.privacy_dsr import ensure_request_metadata, is_overdue


REQUIRED_INCIDENT_SECRETS = [
    "SUPABASE_SERVICE_ROLE_KEY",
    "EVOLVIAN_INTERNAL_TASK_TOKEN",
    "META_APP_SECRET",
    "TWILIO_AUTH_TOKEN",
    "RESEND_API_KEY",
]


def incident_secret_checks() -> list[dict[str, Any]]:
    import os

    checks: list[dict[str, Any]] = []
    for env_name in REQUIRED_INCIDENT_SECRETS:
        checks.append(
            {
                "env": env_name,
                "configured": bool(str(os.getenv(env_name, "")).strip()),
            }
        )
    return checks


def incident_secret_health(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "unknown"
    missing = sum(1 for check in checks if not check.get("configured"))
    if missing == 0:
        return "pass"
    if missing <= 2:
        return "warn"
    return "fail"


def _count_history_failures(*, since_iso: str, max_rows: int) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        response = (
            supabase.table("history")
            .select("id,status,channel,source_type,created_at")
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(max_rows)
            .execute()
        )
        rows = [row for row in (response.data or []) if isinstance(row, dict)]
    except Exception as error:  # noqa: BLE001
        errors.append(str(error))

    failed_statuses = {"failed", "error", "retention_redacted"}
    counts_by_channel: dict[str, int] = {}
    failed = 0
    for row in rows:
        status = str(row.get("status") or "").strip().lower()
        if status not in failed_statuses:
            continue
        failed += 1
        channel = str(row.get("channel") or "unknown")
        counts_by_channel[channel] = counts_by_channel.get(channel, 0) + 1

    return {
        "scanned_rows": len(rows),
        "failed_rows": failed,
        "failed_by_channel": counts_by_channel,
        "errors": errors,
    }


def _count_open_overdue_dsar(*, max_rows: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        response = (
            supabase.table("public_privacy_requests")
            .select("id,status,request_type,details,created_at,source")
            .order("created_at", desc=True)
            .limit(max_rows)
            .execute()
        )
        rows = [row for row in (response.data or []) if isinstance(row, dict)]
    except Exception as error:  # noqa: BLE001
        errors.append(str(error))

    overdue_count = 0
    open_count = 0
    for row in rows:
        row_id = str(row.get("id") or "")
        fallback_request_id = f"dsar_{row_id.replace('-', '').lower()[:12]}" if row_id else "dsar_unknown"
        _, metadata = ensure_request_metadata(record=row, request_id=fallback_request_id)

        status = str(metadata.get("status") or row.get("status") or "").strip().lower()
        if status in {"fulfilled", "denied", "withdrawn"}:
            continue
        open_count += 1
        if is_overdue(metadata, created_at=row.get("created_at")):
            overdue_count += 1

    return {
        "scanned_rows": len(rows),
        "open_count": open_count,
        "overdue_count": overdue_count,
        "errors": errors,
    }


def build_incident_readiness_snapshot(*, window_hours: int = 24, max_rows: int = 2000) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    window_hours = max(1, min(window_hours, 24 * 30))
    max_rows = max(100, min(max_rows, 10000))

    since = now - timedelta(hours=window_hours)
    secret_checks = incident_secret_checks()
    secret_health = incident_secret_health(secret_checks)
    history_failures = _count_history_failures(since_iso=since.isoformat(), max_rows=max_rows)
    dsar_overdue = _count_open_overdue_dsar(max_rows=max_rows)

    return {
        "snapshot_at": now.isoformat(),
        "window_hours": window_hours,
        "max_rows": max_rows,
        "secret_checks": secret_checks,
        "secret_health": secret_health,
        "history_failures": history_failures,
        "dsar_overdue": dsar_overdue,
    }


def render_incident_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Incident Readiness Snapshot",
        "",
        f"- Snapshot at: {snapshot.get('snapshot_at')}",
        f"- Window (hours): {snapshot.get('window_hours')}",
        f"- Secret health: {snapshot.get('secret_health')}",
        "",
        "## Secret Checks",
    ]
    for check in snapshot.get("secret_checks", []):
        mark = "OK" if check.get("configured") else "MISSING"
        lines.append(f"- {check.get('env')}: {mark}")

    history_failures = snapshot.get("history_failures", {})
    lines.extend(
        [
            "",
            "## History Failure Signals",
            f"- Scanned rows: {history_failures.get('scanned_rows', 0)}",
            f"- Failed rows: {history_failures.get('failed_rows', 0)}",
        ]
    )
    failed_by_channel = history_failures.get("failed_by_channel", {})
    if failed_by_channel:
        for channel, count in failed_by_channel.items():
            lines.append(f"- {channel}: {count}")

    dsar = snapshot.get("dsar_overdue", {})
    lines.extend(
        [
            "",
            "## DSAR Timeliness Signals",
            f"- Open requests: {dsar.get('open_count', 0)}",
            f"- Overdue requests: {dsar.get('overdue_count', 0)}",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def write_incident_evidence_bundle(
    *,
    out_dir: Path,
    snapshot: dict[str, Any],
    copy_files: list[Path] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "incident_snapshot.json"
    md_path = out_dir / "incident_snapshot.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_incident_snapshot_markdown(snapshot), encoding="utf-8")

    copied: list[str] = []
    for src in copy_files or []:
        if not src.exists():
            continue
        target = out_dir / src.name
        if src.resolve() == target.resolve():
            continue
        shutil.copy2(src, target)
        copied.append(str(target))

    return {
        "out_dir": str(out_dir),
        "snapshot_json": str(json_path),
        "snapshot_markdown": str(md_path),
        "copied_files": copied,
    }

