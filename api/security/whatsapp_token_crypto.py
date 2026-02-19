import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX_V1 = "enc:v1:"


def _derive_fernet_key(raw_key: str) -> bytes:
    normalized = (raw_key or "").strip()
    if not normalized:
        raise ValueError("missing_whatsapp_token_encryption_key")

    try:
        # Preferred path: already provided as a valid Fernet key.
        Fernet(normalized.encode("utf-8"))
        return normalized.encode("utf-8")
    except Exception:
        # Fallback: deterministic derivation from passphrase-like secret.
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet_optional() -> Optional[Fernet]:
    raw = (os.getenv("WHATSAPP_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    try:
        return Fernet(_derive_fernet_key(raw))
    except Exception:
        logger.exception("❌ Invalid WHATSAPP_TOKEN_ENCRYPTION_KEY")
        return None


def _get_fernet_required() -> Fernet:
    cipher = _get_fernet_optional()
    if not cipher:
        raise RuntimeError(
            "WHATSAPP_TOKEN_ENCRYPTION_KEY is required to store WhatsApp tokens securely"
        )
    return cipher


def is_encrypted_whatsapp_token(value: Optional[str]) -> bool:
    token = str(value or "").strip()
    return token.startswith(_PREFIX_V1)


def encrypt_whatsapp_token(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError("empty_whatsapp_token")

    if is_encrypted_whatsapp_token(token):
        return token

    cipher = _get_fernet_required()
    encrypted = cipher.encrypt(token.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX_V1}{encrypted}"


def decrypt_whatsapp_token(value: Optional[str]) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None

    # Backward compatibility with legacy plaintext rows.
    if not is_encrypted_whatsapp_token(token):
        return token

    cipher = _get_fernet_optional()
    if not cipher:
        logger.error("❌ Cannot decrypt WhatsApp token: WHATSAPP_TOKEN_ENCRYPTION_KEY is missing")
        return None

    encrypted_payload = token[len(_PREFIX_V1):]
    try:
        return cipher.decrypt(encrypted_payload.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("❌ Cannot decrypt WhatsApp token: invalid ciphertext")
        return None
    except Exception:
        logger.exception("❌ Unexpected WhatsApp token decryption failure")
        return None

