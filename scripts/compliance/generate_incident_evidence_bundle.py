#!/usr/bin/env python3
"""
Generate incident readiness evidence bundle.

Usage:
  python scripts/compliance/generate_incident_evidence_bundle.py
  python scripts/compliance/generate_incident_evidence_bundle.py --out-dir docs/compliance/evidence/2026-02
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from api.compliance.incident_readiness import (
    build_incident_readiness_snapshot,
    write_incident_evidence_bundle,
)


def _default_out_dir() -> Path:
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    return Path("docs/compliance/evidence") / month


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate incident readiness evidence bundle.")
    parser.add_argument("--out-dir", type=str, default="", help="Output evidence folder.")
    parser.add_argument("--window-hours", type=int, default=24, help="Observation window in hours.")
    parser.add_argument("--max-rows", type=int, default=2000, help="Max rows to scan per source.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()

    snapshot = build_incident_readiness_snapshot(
        window_hours=args.window_hours,
        max_rows=args.max_rows,
    )

    copy_candidates = [
        Path("docs/compliance/endpoint_control_inventory.csv"),
        Path("docs/compliance/phase2_legal_compliance_matrix.md"),
        Path("docs/compliance/phase2_audit_checklist.md"),
        Path("docs/compliance/phase2_incident_runbook.md"),
        Path("docs/compliance/templates/incident_notification_internal.md"),
        Path("docs/compliance/templates/incident_notification_california.md"),
        Path("docs/compliance/templates/incident_notification_gdpr.md"),
    ]

    result = write_incident_evidence_bundle(
        out_dir=out_dir,
        snapshot=snapshot,
        copy_files=copy_candidates,
    )

    print("Incident evidence bundle generated:")
    print(f"  out_dir: {result['out_dir']}")
    print(f"  snapshot_json: {result['snapshot_json']}")
    print(f"  snapshot_markdown: {result['snapshot_markdown']}")
    print(f"  copied_files: {len(result['copied_files'])}")


if __name__ == "__main__":
    main()

