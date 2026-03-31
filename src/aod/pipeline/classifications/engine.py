"""Main engine for computing derived classifications."""

from datetime import datetime, timedelta
from typing import Optional

from .enums import ActivityStatus
from .result_types import (
    DerivedClassificationSummary,
    DistributionDiagnostic,
    DomainRollup,
)
from .time_utils import ensure_utc_aware, utc_now
from .domain_helpers import resolve_domain_key
from .domain_rollups import compute_domain_rollups
from ...models.output_contracts import Asset, LensStatus
from ...core.policy import get_current_config


def compute_derived_classifications(
    assets: list[Asset],
    activity_window_days: Optional[int] = None,
    aod_discovery_id: Optional[str] = None,
    snapshot_as_of: Optional[datetime] = None
) -> DerivedClassificationSummary:
    """
    Compute derived classifications for all assets.

    Returns summary with counts and detailed lists.

    IMPORTANT: Both counts AND drilldown lists use DOMAIN-AGGREGATED assets.
    This ensures KPI count matches drilldown count. Multiple assets sharing
    the same domain are merged.

    Args:
        assets: List of assets to classify
        activity_window_days: Number of days to consider for recent activity
        aod_discovery_id: Optional run ID for caching (recommended for API routes)
        snapshot_as_of: Reference time for recency calculation

    Returns:
        DerivedClassificationSummary with counts and detailed asset lists
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    reference_time = ensure_utc_aware(snapshot_as_of) if snapshot_as_of else utc_now()
    if reference_time is None:
        reference_time = utc_now()
    cutoff_date = reference_time - timedelta(days=activity_window_days)
    distribution = DistributionDiagnostic(total_assets=len(assets))

    domain_to_assets: dict[str, list[Asset]] = {}

    for asset in assets:
        if asset.lens_status.idp == LensStatus.MATCHED:
            distribution.with_idp_match += 1
        if asset.lens_status.cmdb == LensStatus.MATCHED:
            distribution.with_cmdb_match += 1
        if asset.activity_evidence.latest_activity_at is not None:
            distribution.with_any_activity_timestamp += 1
            latest = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
            if latest is not None and latest > cutoff_date:
                distribution.with_activity_last_30_days += 1

        domain_key, _, _ = resolve_domain_key(asset)
        if domain_key not in domain_to_assets:
            domain_to_assets[domain_key] = []
        domain_to_assets[domain_key].append(asset)

    domain_rollups = compute_domain_rollups(assets, activity_window_days, aod_discovery_id=aod_discovery_id)

    shadow_assets = []
    zombie_assets = []
    parked_assets = []
    indeterminate_count = 0

    for domain_key in sorted(domain_rollups.keys()):
        rollup = domain_rollups[domain_key]
        domain_assets = domain_to_assets.get(domain_key, [])
        if not domain_assets:
            continue

        representative = domain_assets[0]

        vendor_hyp = None
        for a in domain_assets:
            if a.vendor_hypothesis:
                vendor_hyp = {
                    "value": a.vendor_hypothesis.value,
                    "confidence": a.vendor_hypothesis.confidence,
                    "basis": a.vendor_hypothesis.basis
                }
                break

        all_domains = set()
        all_hostnames = set()
        all_uris = set()
        for a in domain_assets:
            if a.identifiers:
                all_domains.update(a.identifiers.domains)
                all_hostnames.update(a.identifiers.hostnames)
                all_uris.update(a.identifiers.uris)

        activity_status = rollup.get_activity_status(activity_window_days, snapshot_as_of)

        base_entry = {
            "asset_id": str(representative.asset_id),
            "name": domain_key if rollup.is_domain_canonical else representative.name,
            "vendor": representative.vendor,
            "vendor_hypothesis": vendor_hyp,
            "asset_type": representative.asset_type.value,
            "environment": representative.environment.value,
            "identifiers": {
                "domains": sorted(all_domains),
                "hostnames": sorted(all_hostnames),
                "uris": sorted(all_uris)
            },
            "lens_status": {
                "idp": representative.lens_status.idp.value,
                "cmdb": representative.lens_status.cmdb.value,
                "cloud": representative.lens_status.cloud.value,
                "finance": representative.lens_status.finance.value
            },
            "lens_coverage": {
                "idp": representative.lens_coverage.idp,
                "cmdb": representative.lens_coverage.cmdb,
                "cloud": representative.lens_coverage.cloud,
                "finance": representative.lens_coverage.finance,
                "discovery": representative.lens_coverage.discovery
            },
            "activity_evidence": {
                "latest_activity_at": rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else None,
                "activity_status": activity_status.value
            },
            "entity_count": rollup.entity_count,
            "aliases": rollup.entity_names if rollup.entity_count > 1 else [],
            "aggregated_evidence": {
                "has_idp": rollup.has_idp,
                "has_cmdb": rollup.has_cmdb,
                "has_finance": rollup.has_finance,
                "has_cloud": rollup.has_cloud,
                "has_discovery": rollup.has_discovery,
                "is_anchored": rollup.is_anchored()
            }
        }

        if rollup.is_shadow(activity_window_days, snapshot_as_of):
            shadow_assets.append({
                **base_entry,
                "classification": "shadow",
                "reason": f"Shadow IT: {domain_key} found via evidence but missing from official systems",
                "evidence_summary": [
                    f"Presence: {', '.join(filter(None, ['finance' if rollup.has_finance else None, 'cloud' if rollup.has_cloud else None, 'discovery' if rollup.has_discovery else None]))}",
                    "Gaps: No IdP match; No CMDB match",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}"
                ]
            })
        elif rollup.is_zombie(activity_window_days, snapshot_as_of):
            anchored_sources = filter(None, [
                'IdP' if rollup.has_idp else None,
                'CMDB' if rollup.has_cmdb else None,
                'Finance' if rollup.has_finance else None,
                'Cloud' if rollup.has_cloud else None
            ])
            zombie_assets.append({
                **base_entry,
                "classification": "zombie",
                "reason": f"Zombie: {domain_key} anchored in systems but has stale activity",
                "evidence_summary": [
                    f"Anchored in: {', '.join(anchored_sources)}",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}"
                ]
            })
        elif rollup.is_parked(activity_window_days, snapshot_as_of):
            parked_assets.append({
                **base_entry,
                "classification": "parked",
                "reason": f"Parked: {domain_key} not anchored in any system and has stale activity - non-actionable",
                "evidence_summary": [
                    "Not anchored: No IdP, CMDB, Finance, or Cloud presence",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}",
                    "Non-actionable: Cannot deprovision what isn't managed"
                ]
            })
        elif not rollup.is_domain_canonical:
            indeterminate_count += 1

    distribution.indeterminate_count = indeterminate_count

    return DerivedClassificationSummary(
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        parked_count=len(parked_assets),
        indeterminate_count=indeterminate_count,
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets,
        parked_assets=parked_assets,
        distribution=distribution,
        domain_rollups=domain_rollups
    )
