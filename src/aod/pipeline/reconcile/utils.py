"""Utility functions for reconciliation module."""

from datetime import datetime, timezone
from typing import Optional

from .enums import ReasonCode


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize a datetime to UTC-aware.

    Args:
        dt: A datetime that may or may not be timezone-aware

    Returns:
        UTC-aware datetime, or None if input is None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def deduplicate_reason_codes(codes: list[ReasonCode]) -> list[ReasonCode]:
    """
    Remove duplicate reason codes while preserving order.

    Args:
        codes: List of reason codes that may contain duplicates

    Returns:
        Deduplicated list with original order preserved
    """
    seen = set()
    result = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


# Underscore aliases for backwards compatibility
_utc_now = utc_now
_ensure_utc_aware = ensure_utc_aware
_deduplicate_reason_codes = deduplicate_reason_codes
