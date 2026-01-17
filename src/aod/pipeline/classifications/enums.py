"""Enums for derived classifications."""

from enum import Enum


class ActivityStatus(str, Enum):
    """
    Activity status for an asset based on timestamp evidence.

    RECENT = has activity timestamp within activity_window_days (active)
    STALE = has activity timestamp outside activity_window_days (inactive)
    NONE = no activity timestamps at all (indeterminate - we don't know)

    Key distinction: NONE means "no evidence" which is different from STALE ("evidence of staleness").
    This matters for zombie classification - we only classify as zombie when we KNOW it's stale.
    """
    RECENT = "recent"
    STALE = "stale"
    NONE = "none"
