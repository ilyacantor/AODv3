"""Domain rollup computation for derived classifications."""

from typing import Optional

from .result_types import DomainRollup
from .domain_helpers import resolve_domain_key, get_parent_domain
from .time_utils import ensure_utc_aware
from ..cache import get_domain_rollups_cache
from ...models.output_contracts import Asset
from ...core.policy import get_current_config


def compute_domain_rollups(
    assets: list[Asset],
    activity_window_days: Optional[int] = None,
    run_id: Optional[str] = None
) -> dict[str, DomainRollup]:
    """
    Compute domain-level rollups using OR logic across entities.

    For reconciliation, governance signals are aggregated at domain level:
    - has_idp = OR(all entities with this domain)
    - has_cmdb = OR(all entities with this domain)
    - etc.

    IMPORTANT: HAS_* means PRESENCE (evidence exists), not admission gate passed.

    ACTIVITY ROLLUP (Zombie Cure): Activity from subdomains is propagated to parent domains.
    e.g., activity on mail.google.com counts as activity for google.com

    Args:
        assets: List of assets to aggregate
        activity_window_days: Activity window for zombie classification (default from policy config)
        run_id: Optional run ID for caching (recommended for API routes)

    Returns:
        Dictionary mapping domain keys to DomainRollup objects
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    # Check cache if run_id is provided
    cache = get_domain_rollups_cache()
    if run_id:
        cache_key = f"run:{run_id}:window:{activity_window_days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    rollups: dict[str, DomainRollup] = {}

    for asset in assets:
        domain_key, is_canonical, alias_keys = resolve_domain_key(asset)

        # Use lens_coverage for governance (reflects gate-validated admission)
        has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
        has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
        has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
        has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
        has_discovery = bool(getattr(asset, "discovery_sources", None))
        has_ongoing_finance = any(
            isinstance(ref, str) and (
                ref.startswith("recurring_contract:") or
                ref.startswith("recurring_transaction:")
            )
            for ref in asset.evidence_refs
        )
        latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)

        if domain_key in rollups:
            r = rollups[domain_key]
            r.has_idp = r.has_idp or has_idp
            r.has_cmdb = r.has_cmdb or has_cmdb
            r.has_finance = r.has_finance or has_finance
            r.has_cloud = r.has_cloud or has_cloud
            r.has_discovery = r.has_discovery or has_discovery
            r.has_ongoing_finance = r.has_ongoing_finance or has_ongoing_finance
            r.entity_names.append(asset.name)
            r.entity_count += 1
            for ak in alias_keys:
                if ak not in r.alias_keys:
                    r.alias_keys.append(ak)
            if latest_activity is not None:
                if r.latest_activity_at is None or latest_activity > r.latest_activity_at:
                    r.latest_activity_at = latest_activity
        else:
            rollups[domain_key] = DomainRollup(
                domain_key=domain_key,
                has_idp=has_idp,
                has_cmdb=has_cmdb,
                has_finance=has_finance,
                has_cloud=has_cloud,
                has_discovery=has_discovery,
                latest_activity_at=latest_activity,
                entity_names=[asset.name],
                entity_count=1,
                is_domain_canonical=is_canonical,
                alias_keys=list(alias_keys),
                has_ongoing_finance=has_ongoing_finance
            )

    # ACTIVITY ROLLUP (Zombie Cure): Propagate activity from subdomains to parent domains
    for domain_key, rollup in list(rollups.items()):
        parent_domain = get_parent_domain(domain_key)
        if parent_domain and parent_domain in rollups:
            parent_rollup = rollups[parent_domain]
            # Propagate activity: if subdomain has more recent activity, use it for parent
            if rollup.latest_activity_at is not None:
                subdomain_activity = ensure_utc_aware(rollup.latest_activity_at)
                parent_activity = ensure_utc_aware(parent_rollup.latest_activity_at)
                if parent_activity is None or (subdomain_activity and subdomain_activity > parent_activity):
                    parent_rollup.latest_activity_at = subdomain_activity

    # Store in cache if run_id is provided
    if run_id:
        cache_key = f"run:{run_id}:window:{activity_window_days}"
        cache.set(cache_key, rollups)

    return rollups
