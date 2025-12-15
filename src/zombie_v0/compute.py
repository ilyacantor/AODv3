"""
Zombie v0 Computation Module

Completely walled-off zombie determination using only facts.
Does NOT reuse existing reconciliation payload logic.

Zombie Definition:
- exists_in_sor = present in any System of Record (IdP, CMDB, Cloud, Finance)
- activity_in_window = any observed_at timestamp within window_days
- zombie = exists_in_sor AND NOT activity_in_window
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID


@dataclass
class ZombieV0Result:
    """Result of zombie v0 determination for a single asset"""
    asset_id: str
    exists_in_sor: bool
    activity_in_window: bool
    zombie: bool
    last_activity_observed_at: Optional[datetime]
    reason: str


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to UTC-aware. Returns None if input is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_zombie_v0_for_asset(
    asset_id: str,
    lens_status_idp: str,
    lens_status_cmdb: str,
    lens_status_cloud: str,
    lens_status_finance: str,
    idp_last_login_at: Optional[datetime],
    discovery_observed_at: Optional[datetime],
    cloud_observed_at: Optional[datetime],
    endpoint_last_seen_at: Optional[datetime],
    network_last_seen_at: Optional[datetime],
    finance_last_transaction_at: Optional[datetime],
    window_days: int
) -> ZombieV0Result:
    """
    Compute zombie status for a single asset using only facts.
    
    No ML, no thresholds, no anomaly scores.
    
    Args:
        asset_id: The asset identifier
        lens_status_*: Lens status for each SOR (matched/unmatched/ambiguous)
        *_at: Activity timestamps from various sources
        window_days: Activity window in days (REQUIRED, no default)
    
    Returns:
        ZombieV0Result with deterministic zombie determination
    """
    sor_sources = []
    if lens_status_idp == "matched":
        sor_sources.append("IdP")
    if lens_status_cmdb == "matched":
        sor_sources.append("CMDB")
    if lens_status_cloud == "matched":
        sor_sources.append("Cloud")
    if lens_status_finance == "matched":
        sor_sources.append("Billing")
    
    exists_in_sor = len(sor_sources) > 0
    
    activity_timestamps: list[tuple[str, datetime]] = []
    
    if idp_last_login_at:
        ts = _ensure_utc_aware(idp_last_login_at)
        if ts:
            activity_timestamps.append(("IdP", ts))
    
    if discovery_observed_at:
        ts = _ensure_utc_aware(discovery_observed_at)
        if ts:
            activity_timestamps.append(("Logs", ts))
    
    if cloud_observed_at:
        ts = _ensure_utc_aware(cloud_observed_at)
        if ts:
            activity_timestamps.append(("Cloud", ts))
    
    if endpoint_last_seen_at:
        ts = _ensure_utc_aware(endpoint_last_seen_at)
        if ts:
            activity_timestamps.append(("Endpoint", ts))
    
    if network_last_seen_at:
        ts = _ensure_utc_aware(network_last_seen_at)
        if ts:
            activity_timestamps.append(("Network", ts))
    
    if finance_last_transaction_at:
        ts = _ensure_utc_aware(finance_last_transaction_at)
        if ts:
            activity_timestamps.append(("Billing", ts))
    
    last_activity: Optional[datetime] = None
    if activity_timestamps:
        last_activity = max(ts for _, ts in activity_timestamps)
    
    cutoff = _utc_now() - timedelta(days=window_days)
    activity_in_window = last_activity is not None and last_activity >= cutoff
    
    zombie = exists_in_sor and not activity_in_window
    
    if not exists_in_sor:
        reason = "Not present in any System of Record."
    elif not activity_timestamps:
        reason = f"Exists in {', '.join(sor_sources)}; no activity observed in IdP/Billing/Logs."
    elif activity_in_window:
        reason = f"Exists in {', '.join(sor_sources)}; activity observed within {window_days} days."
    else:
        reason = f"Exists in {', '.join(sor_sources)}; no activity observed in IdP/Billing/Logs in {window_days} days."
    
    return ZombieV0Result(
        asset_id=asset_id,
        exists_in_sor=exists_in_sor,
        activity_in_window=activity_in_window,
        zombie=zombie,
        last_activity_observed_at=last_activity,
        reason=reason
    )


async def compute_zombies_v0(run_id: str, window_days: int) -> list[ZombieV0Result]:
    """
    Compute zombie v0 status for all assets in a run.
    
    This function is completely walled-off from the main pipeline.
    It fetches assets directly from the database and computes zombie status.
    
    Args:
        run_id: The run ID to fetch assets for
        window_days: Activity window in days (REQUIRED, no default)
    
    Returns:
        List of ZombieV0Result for each asset
    """
    from aod.db.database import get_db
    
    db = await get_db()
    pool = await db.get_pool()
    
    query = """
        SELECT 
            asset_id,
            lens_status_idp,
            lens_status_cmdb,
            lens_status_cloud,
            lens_status_finance,
            idp_last_login_at,
            discovery_observed_at,
            cloud_observed_at,
            endpoint_last_seen_at,
            network_last_seen_at,
            finance_last_transaction_at
        FROM assets
        WHERE run_id = $1
        ORDER BY asset_id
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, run_id)
    
    results = []
    for row in rows:
        result = compute_zombie_v0_for_asset(
            asset_id=str(row["asset_id"]),
            lens_status_idp=row.get("lens_status_idp", "unmatched") or "unmatched",
            lens_status_cmdb=row.get("lens_status_cmdb", "unmatched") or "unmatched",
            lens_status_cloud=row.get("lens_status_cloud", "unmatched") or "unmatched",
            lens_status_finance=row.get("lens_status_finance", "unmatched") or "unmatched",
            idp_last_login_at=row.get("idp_last_login_at"),
            discovery_observed_at=row.get("discovery_observed_at"),
            cloud_observed_at=row.get("cloud_observed_at"),
            endpoint_last_seen_at=row.get("endpoint_last_seen_at"),
            network_last_seen_at=row.get("network_last_seen_at"),
            finance_last_transaction_at=row.get("finance_last_transaction_at"),
            window_days=window_days
        )
        results.append(result)
    
    return results
