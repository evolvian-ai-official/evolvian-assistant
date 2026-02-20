"""
One-time backfill script to encrypt legacy plaintext WhatsApp tokens in `channels`.

Usage:
  WHATSAPP_TOKEN_ENCRYPTION_KEY=... PYTHONPATH=. python scripts/reencrypt_whatsapp_tokens.py
"""

from api.config.config import supabase
from api.security.whatsapp_token_crypto import (
    encrypt_whatsapp_token,
    is_encrypted_whatsapp_token,
)


def main() -> None:
    response = (
        supabase
        .table("channels")
        .select("id, wa_token")
        .eq("type", "whatsapp")
        .execute()
    )

    rows = response.data or []
    if not rows:
        print("No WhatsApp channel tokens found.")
        return

    scanned = 0
    updated = 0
    skipped = 0

    for row in rows:
        scanned += 1
        row_id = str(row.get("id") or "").strip()
        raw_token = str(row.get("wa_token") or "").strip()

        if not row_id or not raw_token:
            skipped += 1
            continue

        if is_encrypted_whatsapp_token(raw_token):
            skipped += 1
            continue

        encrypted = encrypt_whatsapp_token(raw_token)

        (
            supabase
            .table("channels")
            .update({"wa_token": encrypted})
            .eq("id", row_id)
            .execute()
        )
        updated += 1

    print(
        f"Backfill complete. scanned={scanned} updated={updated} skipped={skipped}"
    )


if __name__ == "__main__":
    main()
