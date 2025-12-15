"""Zombie v0 logic - completely isolated, written from scratch.

This module does NOT import or reuse any existing AOD zombie logic.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from .types import ZombieV0Result


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if dt_str is None:
        return None
    try:
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_zombie_v0(
    asset_id: str,
    lens_status: dict,
    activity_evidence: dict,
    window_days: int
) -> ZombieV0Result:
    """
    Classify a single asset as zombie or not.
    
    Zombie rule (binary):
        zombie = exists_in_sor AND NOT activity_in_window
    
    Exists = asset appears in any system of record:
        - CMDB
        - Billing (Finance)
        - IdP
        - Cloud inventory
    
    Activity = any observed_at >= now - window_days
    """
    has_idp = lens_status.get("idp") == "matched"
    has_cmdb = lens_status.get("cmdb") == "matched"
    has_cloud = lens_status.get("cloud") == "matched"
    has_finance = lens_status.get("finance") == "matched"
    
    exists_in_sor = has_idp or has_cmdb or has_cloud or has_finance
    
    sor_list = []
    if has_cmdb:
        sor_list.append("CMDB")
    if has_finance:
        sor_list.append("Billing")
    if has_idp:
        sor_list.append("IdP")
    if has_cloud:
        sor_list.append("Cloud")
    
    activity_timestamps = []
    
    if activity_evidence.get("idp_last_login_at"):
        ts = _parse_datetime(activity_evidence["idp_last_login_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("discovery_observed_at"):
        ts = _parse_datetime(activity_evidence["discovery_observed_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("cloud_observed_at"):
        ts = _parse_datetime(activity_evidence["cloud_observed_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("endpoint_last_seen_at"):
        ts = _parse_datetime(activity_evidence["endpoint_last_seen_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("network_last_seen_at"):
        ts = _parse_datetime(activity_evidence["network_last_seen_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("finance_last_transaction_at"):
        ts = _parse_datetime(activity_evidence["finance_last_transaction_at"])
        if ts:
            activity_timestamps.append(ts)
    
    if activity_evidence.get("latest_activity_at"):
        ts = _parse_datetime(activity_evidence["latest_activity_at"])
        if ts:
            activity_timestamps.append(ts)
    
    last_activity: Optional[datetime] = None
    if activity_timestamps:
        utc_timestamps = [_ensure_utc(ts) for ts in activity_timestamps if ts is not None]
        if utc_timestamps:
            last_activity = max(t for t in utc_timestamps if t is not None)
    
    cutoff = _utc_now() - timedelta(days=window_days)
    
    activity_in_window = False
    if last_activity is not None and last_activity >= cutoff:
        activity_in_window = True
    
    zombie = exists_in_sor and not activity_in_window
    
    if not exists_in_sor:
        reason = "Does not exist in any system of record."
    elif zombie and last_activity is None:
        reason = f"Exists in {', '.join(sor_list)}; no activity observed in last {window_days} days."
    elif zombie:
        reason = f"Exists in {', '.join(sor_list)}; no activity observed in last {window_days} days."
    else:
        reason = f"Exists in {', '.join(sor_list)}; has recent activity within {window_days} days."
    
    return ZombieV0Result(
        asset_id=asset_id,
        exists_in_sor=exists_in_sor,
        activity_in_window=activity_in_window,
        zombie=zombie,
        last_activity_observed_at=last_activity.isoformat() if last_activity else None,
        reason=reason
    )
