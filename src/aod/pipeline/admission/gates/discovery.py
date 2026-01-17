"""Discovery admission gate - check discovery corroboration criteria."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from ....models.input_contracts import Observation
from ..constants import SOURCE_TO_PLANE, DISCOVERY_CORROBORATION_PLANES

logger = logging.getLogger(__name__)


def source_to_plane(source: str) -> Optional[str]:
    """
    Map a source to its parent plane.

    Returns None for unknown sources to ensure they don't contribute to plane diversity.
    Unknown sources are quarantined from counting to prevent signal inflation.
    """
    return SOURCE_TO_PLANE.get(source.lower())


@dataclass
class DiscoveryFootprint:
    """Evidence footprint for discovery admission."""
    discovery_sources: set
    planes_present: set
    recent_activity: bool
    latest_activity_at: Optional[datetime]
    reason_codes: list


def build_discovery_footprint(
    observations: Optional[list[Observation]],
    canonical_key: Optional[str] = None,
    snapshot_timestamp: Optional[datetime] = None,
    activity_window_days: Optional[int] = None
) -> DiscoveryFootprint:
    """
    Build an evidence footprint for a CandidateEntity's discovery observations.

    Counts sources with RECENT activity relative to SNAPSHOT timestamp. Farm uses
    the snapshot generation timestamp as the reference point for the 90-day activity
    window, not the current time. This ensures consistent results across runs.

    Returns:
        DiscoveryFootprint with:
        - discovery_sources: set of distinct source names WITH RECENT ACTIVITY
        - planes_present: set of mapped planes with recent activity
        - recent_activity: True if any observation is within 90 days of snapshot
        - latest_activity_at: timestamp of most recent observation
        - reason_codes: list of reason codes for this footprint
    """
    from ....core.policy import get_current_config

    # Load activity window from policy if not provided
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.discovery_activity_window_days

    all_discovery_sources: set = set()
    all_planes_present: set = set()
    latest_activity: Optional[datetime] = None
    reason_codes: list = []

    if not observations:
        return DiscoveryFootprint(
            discovery_sources=set(),
            planes_present=set(),
            recent_activity=False,
            latest_activity_at=None,
            reason_codes=["NO_DISCOVERY"]
        )

    # Calculate cutoff for recent activity - use snapshot timestamp as reference if provided
    # Farm uses snapshot timestamp, not current time, for consistent 90-day windows
    reference_time = snapshot_timestamp if snapshot_timestamp else datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    cutoff = reference_time - timedelta(days=activity_window_days)

    # Count only sources with RECENT activity (using snapshot timestamp as reference)
    # Farm's policy: count sources where the observation is within 90 days of snapshot
    for obs in observations:
        # Track latest activity timestamp
        if obs.observed_at:
            obs_time = obs.observed_at
            if obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)
            if latest_activity is None or obs_time > latest_activity:
                latest_activity = obs_time

        # Only count sources with RECENT activity (within 90 days of snapshot)
        if obs.source and obs.observed_at:
            obs_time = obs.observed_at
            if obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)

            # Only count if observation is recent relative to snapshot timestamp
            if obs_time >= cutoff:
                source_lower = obs.source.lower()
                plane = source_to_plane(source_lower)
                # Only count sources that map to discovery-corroboration planes
                # Exclude CMDB and finance sources as they aren't "real" discovery evidence
                if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                    all_discovery_sources.add(source_lower)
                    all_planes_present.add(plane)

    recent_activity = latest_activity is not None and latest_activity >= cutoff

    # Use the sources with recent activity
    discovery_sources = all_discovery_sources
    planes_present = all_planes_present

    min_sources = get_current_config().admission_gates.noise_floor
    if len(discovery_sources) >= min_sources:
        reason_codes.append(f"DISCOVERY_SOURCE_COUNT_GE_{min_sources}")
    else:
        reason_codes.append(f"DISCOVERY_SOURCE_COUNT_LT_{min_sources}")

    if len(planes_present) >= 2:
        reason_codes.append("PLANE_DIVERSITY_GE_2")
    else:
        reason_codes.append("PLANE_DIVERSITY_LT_2")

    if discovery_sources:
        reason_codes.append("HAS_DISCOVERY")
    else:
        reason_codes.append("NO_DISCOVERY")

    if recent_activity:
        reason_codes.append("RECENT_ACTIVITY")
    elif latest_activity:
        reason_codes.append("STALE_ACTIVITY")
    else:
        reason_codes.append("NO_ACTIVITY_TIMESTAMPS")

    return DiscoveryFootprint(
        discovery_sources=discovery_sources,
        planes_present=planes_present,
        recent_activity=recent_activity,
        latest_activity_at=latest_activity,
        reason_codes=reason_codes
    )


def check_discovery_admission(
    observations: Optional[list[Observation]],
    min_sources: Optional[int] = None,
    canonical_key: Optional[str] = None,
    snapshot_timestamp: Optional[datetime] = None
) -> tuple[bool, str]:
    """
    Check discovery-only admission criteria.

    Admit discovery-only candidates when usage is corroborated and recent:
    - Evidence from ≥2 distinct DISCOVERY SOURCES (not planes!)
    - Recent activity ≤ 90 days

    CRITICAL FIX (Dec 2025):
    - Gate on distinct SOURCES (browser, proxy, dns = 3 sources) NOT distinct planes
    - Plane diversity is an annotation/confidence signal, NOT an admission blocker
    - This fixes shadow misses where assets like asana.com with 3 sources
      (browser, proxy, dns) were rejected because they all map to "network" plane

    Args:
        observations: List of discovery observations
        min_sources: Minimum distinct sources required (default from policy: noise_floor)
        canonical_key: Entity key for debug logging
        snapshot_timestamp: Snapshot timestamp for 90-day window reference

    Returns:
        Tuple of (admitted: bool, reason: str)
    """
    from ....core.policy import get_current_config
    if min_sources is None:
        min_sources = get_current_config().admission_gates.noise_floor

    footprint = build_discovery_footprint(observations, canonical_key, snapshot_timestamp)

    source_count = len(footprint.discovery_sources)
    plane_count = len(footprint.planes_present)

    if source_count < min_sources:
        if canonical_key:
            logger.debug(
                f"DISCOVERY_ADMISSION_FAIL: {canonical_key} | "
                f"sources={sorted(footprint.discovery_sources)} (count={source_count}) | "
                f"planes={sorted(footprint.planes_present)} (count={plane_count}) | "
                f"recent_activity={footprint.recent_activity}"
            )
        return False, ""

    if not footprint.recent_activity:
        if canonical_key:
            logger.debug(
                f"DISCOVERY_ADMISSION_FAIL: {canonical_key} | "
                f"sources={sorted(footprint.discovery_sources)} (count={source_count}) | "
                f"planes={sorted(footprint.planes_present)} (count={plane_count}) | "
                f"recent_activity={footprint.recent_activity} | "
                f"latest_activity={footprint.latest_activity_at}"
            )
        return False, ""

    plane_note = f", {plane_count} planes" if plane_count >= 2 else ""
    activity_date = footprint.latest_activity_at.date() if footprint.latest_activity_at else "unknown"

    return True, f"Discovery: {source_count} sources ({', '.join(sorted(footprint.discovery_sources))}){plane_note}, last activity {activity_date}"
