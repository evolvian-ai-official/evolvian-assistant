"""
Backfill provider in history rows.

Usage examples:
  python -m api.internal.backfill_history_provider --dry-run
  python -m api.internal.backfill_history_provider --dry-run --since 2025-01-01T00:00:00Z
  python -m api.internal.backfill_history_provider --apply
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from api.config.config import supabase


UNKNOWN_PROVIDER_VALUES = {"", "internal", "unknown", "none", "null"}
SUPPORTED_PROVIDERS = {"meta", "twilio", "gmail", "widget", "api", "internal"}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _provider_from_metadata(metadata: dict[str, Any]) -> str | None:
    if not metadata:
        return None

    direct_keys = [
        "provider",
        "source_provider",
        "integration_provider",
        "gateway",
        "origin",
    ]
    for key in direct_keys:
        value = _norm(metadata.get(key))
        if value in SUPPORTED_PROVIDERS:
            return value
        if "twilio" in value:
            return "twilio"
        if "meta" in value:
            return "meta"
        if "gmail" in value:
            return "gmail"

    return None


def infer_provider(
    row: dict[str, Any],
    *,
    whatsapp_default_provider: str,
    aggressive_chat_as_api: bool,
) -> str | None:
    channel = _norm(row.get("channel"))
    session_id = _norm(row.get("session_id"))
    metadata = _parse_metadata(row.get("metadata"))

    from_metadata = _provider_from_metadata(metadata)
    if from_metadata:
        return from_metadata

    if channel == "email":
        return "gmail"

    if channel == "whatsapp":
        if "twilio" in session_id:
            return "twilio"
        return whatsapp_default_provider

    if channel == "widget":
        return "widget"

    if aggressive_chat_as_api and channel == "chat":
        return "api"

    return None


def chunked(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill history.provider")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry-run).")
    parser.add_argument("--dry-run", action="store_true", help="Preview updates only.")
    parser.add_argument("--since", type=str, default=None, help="ISO datetime lower bound for created_at.")
    parser.add_argument("--batch-size", type=int, default=1000, help="Read batch size.")
    parser.add_argument("--update-chunk-size", type=int, default=200, help="Rows per update query.")
    parser.add_argument("--max-rows", type=int, default=0, help="Stop after scanning this many rows (0 = all).")
    parser.add_argument(
        "--whatsapp-default-provider",
        type=str,
        default="meta",
        choices=["meta", "twilio"],
        help="Provider to use for whatsapp rows when it cannot be inferred.",
    )
    parser.add_argument(
        "--aggressive-chat-as-api",
        action="store_true",
        help="Also map channel=chat unknown rows to provider=api.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Also re-evaluate rows that already have non-internal provider values.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dry_run = not args.apply or args.dry_run

    scanned = 0
    matched = 0
    planned = 0
    offset = 0

    updates_by_provider: dict[str, list[str]] = {}
    preview: list[tuple[str, str, str, str]] = []

    while True:
        query = (
            supabase.table("history")
            .select("id, provider, channel, session_id, source_type, metadata, created_at")
            .order("created_at", desc=False)
            .range(offset, offset + args.batch_size - 1)
        )
        if args.since:
            query = query.gte("created_at", args.since)

        response = query.execute()
        rows = response.data or []
        if not rows:
            break

        for row in rows:
            scanned += 1
            if args.max_rows and scanned > args.max_rows:
                break

            current_provider = _norm(row.get("provider"))
            candidate_unknown = current_provider in UNKNOWN_PROVIDER_VALUES
            if not args.force and not candidate_unknown:
                continue

            matched += 1

            new_provider = infer_provider(
                row,
                whatsapp_default_provider=args.whatsapp_default_provider,
                aggressive_chat_as_api=args.aggressive_chat_as_api,
            )
            if not new_provider:
                continue
            if current_provider == new_provider:
                continue

            row_id = str(row.get("id"))
            if not row_id:
                continue

            updates_by_provider.setdefault(new_provider, []).append(row_id)
            planned += 1

            if len(preview) < 30:
                preview.append(
                    (
                        row_id,
                        _norm(row.get("channel")),
                        current_provider or "null",
                        new_provider,
                    )
                )

        if args.max_rows and scanned >= args.max_rows:
            break

        offset += args.batch_size

    print(f"Scanned rows: {scanned}")
    print(f"Candidate unknown/internal rows: {matched}")
    print(f"Rows with planned provider changes: {planned}")

    if preview:
        print("\nPreview (up to 30 rows):")
        for row_id, channel, old_provider, new_provider in preview:
            print(f"  id={row_id} channel={channel} provider:{old_provider}->{new_provider}")

    if dry_run:
        print("\nDry-run mode: no updates were written.")
        return

    if planned == 0:
        print("\nNo rows to update.")
        return

    updated = 0
    for provider, ids in updates_by_provider.items():
        for id_chunk in chunked(ids, args.update_chunk_size):
            supabase.table("history").update({"provider": provider}).in_("id", id_chunk).execute()
            updated += len(id_chunk)

    print(f"\nApplied updates: {updated}")


if __name__ == "__main__":
    main()
