#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_")
    return normalized or "unknown"


def _load_inventory(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    dpa_counter: Counter[str] = Counter()
    scc_counter: Counter[str] = Counter()

    for row in rows:
        dpa_counter[_normalize_status(row.get("dpa_status"))] += 1
        scc_counter[_normalize_status(row.get("scc_status"))] += 1

    return {
        "vendor_count": len(rows),
        "dpa_status_counts": dict(sorted(dpa_counter.items())),
        "scc_status_counts": dict(sorted(scc_counter.items())),
    }


def _render_markdown(*, generated_at: str, csv_path: Path, rows: list[dict[str, str]], summary: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Vendor Inventory Snapshot")
    lines.append("")
    lines.append(f"Generated at (UTC): {generated_at}")
    lines.append(f"Source CSV: `{csv_path.as_posix()}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Vendors: {summary['vendor_count']}")
    lines.append(f"- DPA status counts: {summary['dpa_status_counts']}")
    lines.append(f"- SCC status counts: {summary['scc_status_counts']}")
    lines.append("")

    lines.append("## Inventory")
    lines.append("")
    lines.append("| Vendor | DPA Status | SCC Status | Last Reviewed |")
    lines.append("|---|---|---|---|")
    for row in rows:
        lines.append(
            "| {vendor} | {dpa} | {scc} | {reviewed} |".format(
                vendor=row.get("vendor", ""),
                dpa=row.get("dpa_status", ""),
                scc=row.get("scc_status", ""),
                reviewed=row.get("last_reviewed", ""),
            )
        )

    lines.append("")
    return "\n".join(lines)


def generate_snapshot(*, csv_path: Path, out_dir: Path) -> tuple[Path, Path]:
    rows = _load_inventory(csv_path)
    summary = _summarize(rows)
    generated_at = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "generated_at": generated_at,
        "source_csv": str(csv_path),
        "summary": summary,
        "vendors": rows,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "vendor_inventory_snapshot.json"
    md_path = out_dir / "vendor_inventory_snapshot.md"

    json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(
        _render_markdown(
            generated_at=generated_at,
            csv_path=csv_path,
            rows=rows,
            summary=summary,
        ),
        encoding="utf-8",
    )

    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate vendor governance evidence snapshot")
    parser.add_argument(
        "--csv",
        default="docs/compliance/vendor_processor_inventory.csv",
        help="Path to vendor inventory CSV",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output folder for snapshot files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    out_dir = Path(args.out_dir)

    if not csv_path.exists():
        raise SystemExit(f"Inventory CSV not found: {csv_path}")

    json_path, md_path = generate_snapshot(csv_path=csv_path, out_dir=out_dir)
    print("Vendor inventory snapshot generated:")
    print(f"  json: {json_path}")
    print(f"  markdown: {md_path}")


if __name__ == "__main__":
    main()
