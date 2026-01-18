"""Time utilities for derived classifications."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from .enums import ActivityStatus
from ...core.policy import get_current_config


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


def get_activity_status(
    latest_activity_at: Optional[datetime],
    activity_window_days: Optional[int] = None,
    snapshot_as_of: Optional[datetime] = None
) -> ActivityStatus:
    """
    Determine the activity status based on the latest activity timestamp.

    Args:
        latest_activity_at: The latest activity timestamp (may be None)
        activity_window_days: Number of days for the activity window (default from policy config)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now).
                       When processing historical snapshots, use the snapshot's generated_at
                       to avoid falsely marking active assets as stale.

    Returns:
        ActivityStatus.RECENT if activity is within window
        ActivityStatus.STALE if activity is outside window
        ActivityStatus.NONE if no activity timestamp exists
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    if latest_activity_at is None:
        return ActivityStatus.NONE

    latest = ensure_utc_aware(latest_activity_at)
    if latest is None:
        return ActivityStatus.NONE

    reference_time = ensure_utc_aware(snapshot_as_of) if snapshot_as_of else utc_now()
    if reference_time is None:
        reference_time = utc_now()
    cutoff = reference_time - timedelta(days=activity_window_days)

    if latest >= cutoff:
        return ActivityStatus.RECENT
    else:
        return ActivityStatus.STALE


# Underscore aliases for backwards compatibility
_utc_now = utc_now
_ensure_utc_aware = ensure_utc_aware
