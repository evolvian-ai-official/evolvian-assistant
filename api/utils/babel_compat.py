from __future__ import annotations

from datetime import datetime

try:
    from babel.dates import format_datetime as _babel_format_datetime
except Exception:  # pragma: no cover - allow environments without Babel
    _babel_format_datetime = None


_TOKEN_MAP = (
    ("yyyy", "%Y"),
    ("MMMM", "%B"),
    ("MMM", "%b"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("EEEE", "%A"),
    ("EEE", "%a"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("a", "%p"),
)


def _babel_pattern_to_strftime(pattern: str) -> str:
    if not pattern:
        return "%Y-%m-%d %H:%M"
    out = pattern.replace("''", "'")
    # Preserve literal segments like: EEEE dd 'de' MMMM yyyy, HH:mm
    out = out.replace("'de'", "de")
    for src, dst in _TOKEN_MAP:
        out = out.replace(src, dst)
    return out


def format_datetime(value: datetime, pattern: str, locale: str | None = None) -> str:
    if _babel_format_datetime:
        return _babel_format_datetime(value, pattern, locale=locale)
    try:
        return value.strftime(_babel_pattern_to_strftime(pattern))
    except Exception:
        return value.isoformat()
