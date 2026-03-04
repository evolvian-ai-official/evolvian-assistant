import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX_V1 = "cid:v1:"


def _derive_fernet_key(raw_key: str) -> bytes:
    normalized = (raw_key or "").strip()
    if not normalized:
        raise ValueError("missing_unsubscribe_link_encryption_key")

    try:
        Fernet(normalized.encode("utf-8"))
        return normalized.encode("utf-8")
    except Exception:
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


def _load_raw_secret() -> str:
    return (
        os.getenv("UNSUBSCRIBE_LINK_ENCRYPTION_KEY")
        or os.getenv("GOOGLE_OAUTH_STATE_SECRET")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()


@lru_cache(maxsize=1)
def _get_fernet_optional() -> Optional[Fernet]:
    raw = _load_raw_secret()
    if not raw:
        return None
    try:
        return Fernet(_derive_fernet_key(raw))
    except Exception:
        logger.exception("❌ Invalid unsubscribe client-id encryption key")
        return None


def _get_fernet_required() -> Fernet:
    cipher = _get_fernet_optional()
    if not cipher:
        raise RuntimeError(
            "UNSUBSCRIBE_LINK_ENCRYPTION_KEY (or fallback secrets) is required to encrypt unsubscribe client_id"
        )
    return cipher


def is_encrypted_unsubscribe_client_id(value: Optional[str]) -> bool:
    token = str(value or "").strip()
    return token.startswith(_PREFIX_V1)


def encrypt_unsubscribe_client_id(value: str) -> str:
    client_id = str(value or "").strip()
    if not client_id:
        raise ValueError("empty_unsubscribe_client_id")

    if is_encrypted_unsubscribe_client_id(client_id):
        return client_id

    cipher = _get_fernet_required()
    encrypted = cipher.encrypt(client_id.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX_V1}{encrypted}"


def decrypt_unsubscribe_client_id(value: Optional[str]) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None

    # Backward compatibility for legacy plain client_id links.
    if not is_encrypted_unsubscribe_client_id(token):
        return token

    cipher = _get_fernet_optional()
    if not cipher:
        logger.error("❌ Cannot decrypt unsubscribe client_id: encryption key is missing")
        return None

    encrypted_payload = token[len(_PREFIX_V1):]
    try:
        decrypted = cipher.decrypt(encrypted_payload.encode("utf-8")).decode("utf-8").strip()
        return decrypted or None
    except InvalidToken:
        logger.warning("⚠️ Invalid encrypted unsubscribe client_id token")
        return None
    except Exception:
        logger.exception("❌ Unexpected unsubscribe client_id decryption failure")
        return None
