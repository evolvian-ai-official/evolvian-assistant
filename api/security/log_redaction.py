import builtins
import logging
import re
from typing import Any

_REDACTED = "***redacted***"

_SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "gmail_access_token",
    "gmail_refresh_token",
    "wa_token",
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
}

_SENSITIVE_KEYS_PATTERN = (
    r"access_token|refresh_token|gmail_access_token|gmail_refresh_token|"
    r"wa_token|authorization|api_key|apikey|secret|password|token"
)

_JSON_DOUBLE_QUOTE_PATTERN = re.compile(
    rf'("(?:(?:{_SENSITIVE_KEYS_PATTERN}))"\s*:\s*")([^"]+)(")',
    re.IGNORECASE,
)
_JSON_SINGLE_QUOTE_PATTERN = re.compile(
    rf"('(?:(?:{_SENSITIVE_KEYS_PATTERN}))'\s*:\s*')([^']+)(')",
    re.IGNORECASE,
)
_PLAIN_KEY_VALUE_PATTERN = re.compile(
    rf"\b({_SENSITIVE_KEYS_PATTERN})\b\s*[:=]\s*(?:Bearer\s+)?([^\s,;]+)",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"\b(Bearer)\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_GOOGLE_ACCESS_PATTERN = re.compile(r"\bya29\.[A-Za-z0-9._\-]+\b")
_GOOGLE_REFRESH_PATTERN = re.compile(r"\b1//[A-Za-z0-9._\-]+\b")
_META_TOKEN_PATTERN = re.compile(r"\bEAA[A-Za-z0-9._\-]+\b")
_JWT_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")

_LOG_FACTORY_INSTALLED = False
_PRINT_INSTALLED = False
_ORIGINAL_LOG_FACTORY = logging.getLogRecordFactory()
_ORIGINAL_PRINT = builtins.print


def _is_sensitive_key(key: Any) -> bool:
    key_str = str(key or "").strip().lower()
    return key_str in _SENSITIVE_KEYS or key_str.endswith("_token")


def _redact_string(value: str) -> str:
    if not value:
        return value

    result = value

    # JSON-like key/value strings.
    result = _JSON_DOUBLE_QUOTE_PATTERN.sub(r"\1" + _REDACTED + r"\3", result)
    result = _JSON_SINGLE_QUOTE_PATTERN.sub(r"\1" + _REDACTED + r"\3", result)

    # Plain key=value / key: value.
    result = _PLAIN_KEY_VALUE_PATTERN.sub(r"\1: " + _REDACTED, result)

    # Bearer tokens in free text.
    result = _BEARER_PATTERN.sub(r"\1 " + _REDACTED, result)

    # Common provider token formats.
    result = _GOOGLE_ACCESS_PATTERN.sub(_REDACTED, result)
    result = _GOOGLE_REFRESH_PATTERN.sub(_REDACTED, result)
    result = _META_TOKEN_PATTERN.sub(_REDACTED, result)
    result = _JWT_PATTERN.sub(_REDACTED, result)

    return result


def sanitize_for_logging(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (_REDACTED if _is_sensitive_key(key) else sanitize_for_logging(val))
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [sanitize_for_logging(v) for v in value]

    if isinstance(value, tuple):
        return tuple(sanitize_for_logging(v) for v in value)

    if isinstance(value, set):
        return {sanitize_for_logging(v) for v in value}

    if isinstance(value, str):
        return _redact_string(value)

    return value


def _redacting_log_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    record = _ORIGINAL_LOG_FACTORY(*args, **kwargs)

    try:
        record.msg = sanitize_for_logging(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: sanitize_for_logging(val) for key, val in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_for_logging(arg) for arg in record.args)
            else:
                record.args = sanitize_for_logging(record.args)
    except Exception:
        # Logging redaction should never break app execution.
        pass

    return record


def install_logging_redaction() -> None:
    global _LOG_FACTORY_INSTALLED
    if _LOG_FACTORY_INSTALLED:
        return

    logging.setLogRecordFactory(_redacting_log_record_factory)
    _LOG_FACTORY_INSTALLED = True


def install_print_redaction() -> None:
    global _PRINT_INSTALLED
    if _PRINT_INSTALLED:
        return

    def _safe_print(*args: Any, **kwargs: Any) -> None:
        safe_args = tuple(sanitize_for_logging(arg) for arg in args)
        _ORIGINAL_PRINT(*safe_args, **kwargs)

    builtins.print = _safe_print
    _PRINT_INSTALLED = True
