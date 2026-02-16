import hmac
import hashlib
import logging
import os
from typing import Mapping

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator


logger = logging.getLogger(__name__)


def _is_enabled(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def verify_twilio_signature(request: Request, form_data: Mapping[str, str]) -> None:
    """
    Verifica X-Twilio-Signature.

    Compatibilidad:
    - Si TWILIO_VERIFY_SIGNATURE=false => deshabilita validación.
    - Si TWILIO_AUTH_TOKEN no está definido => no bloquea (solo warning).
    """
    if not _is_enabled(os.getenv("TWILIO_VERIFY_SIGNATURE"), default=True):
        return

    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth_token:
        logger.warning("⚠️ TWILIO_AUTH_TOKEN no configurado; se omite verificación de firma.")
        return

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing_twilio_signature",
        )

    validator = RequestValidator(auth_token)
    is_valid = validator.validate(str(request.url), dict(form_data), signature)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_twilio_signature",
        )


def verify_meta_signature(request: Request, raw_body: bytes) -> None:
    """
    Verifica X-Hub-Signature-256 (sha256=...).

    Compatibilidad:
    - Si META_VERIFY_SIGNATURE=false => deshabilita validación.
    - Si META_APP_SECRET no está definido => no bloquea (solo warning).
    """
    if not _is_enabled(os.getenv("META_VERIFY_SIGNATURE"), default=True):
        return

    app_secret = os.getenv("META_APP_SECRET")
    if not app_secret:
        logger.warning("⚠️ META_APP_SECRET no configurado; se omite verificación de firma.")
        return

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing_meta_signature",
        )

    provided_sig = signature_header.split("=", 1)[1]
    expected_sig = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_meta_signature",
        )
