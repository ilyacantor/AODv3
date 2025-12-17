"""
Derived Classifications Module

Computes Shadow and Zombie classifications from evidence AFTER the main pipeline.
These are computed on-read, not stored as flags.

Shadow Asset = admitted asset with:
  - finance evidence OR cloud presence OR discovery (corroborated usage from >=2 sources)
  - AND no IdP match (no SSO / SCIM / service principal)
  - AND no CMDB match
  - AND has recent activity (within activity_window_days)

Zombie Asset = admitted asset with:
  - CMDB or IdP presence
  - AND no activity timestamps OR activity outside activity_window_days
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from ..models.output_contracts import Asset, LensStatus
from .vendor_inference import DOMAIN_TO_VENDOR


def _build_vendor_to_domain_map() -> dict[str, str]:
    """Build reverse mapping from vendor name to canonical domain."""
    vendor_to_domain: dict[str, str] = {}
    for domain, vendor in DOMAIN_TO_VENDOR.items():
        vendor_key = vendor.lower().strip()
        if vendor_key not in vendor_to_domain:
            vendor_to_domain[vendor_key] = domain
        else:
            current = vendor_to_domain[vendor_key]
            if domain.endswith(('.com', '.so', '.io', '.us')) and not current.endswith(('.com', '.so', '.io', '.us')):
                vendor_to_domain[vendor_key] = domain
    return vendor_to_domain


VENDOR_TO_DOMAIN = _build_vendor_to_domain_map()


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


@dataclass
class ClassificationResult:
    """Result of a derived classification check"""
    is_classified: bool
    is_indeterminate: bool
    classification_type: str
    reason: str
    evidence_summary: list[str]


@dataclass
class DistributionDiagnostic:
    """Diagnostic information about asset distribution"""
    total_assets: int = 0
    with_idp_match: int = 0
    with_cmdb_match: int = 0
    with_activity_last_30_days: int = 0
    with_any_activity_timestamp: int = 0
    indeterminate_count: int = 0


@dataclass
class DomainRollup:
    """Aggregated governance signals for a domain (OR logic across entities)"""
    domain_key: str
    has_idp: bool
    has_cmdb: bool
    has_finance: bool
    has_cloud: bool
    has_discovery: bool
    latest_activity_at: Optional[datetime]
    entity_names: list[str]
    entity_count: int
    is_domain_canonical: bool = True
    
    def is_shadow(self, activity_window_days: int = 90) -> bool:
        """
        Domain-level shadow: no governance + has existence evidence + recent activity.
        
        INVARIANT: Only domain-canonical assets count as shadow.
        Internal identifiers (name-derived keys) are excluded from shadow counts.
        """
        if not self.is_domain_canonical:
            return False
        
        has_governance = self.has_idp or self.has_cmdb
        has_existence = self.has_finance or self.has_cloud or self.has_discovery
        
        if has_governance or not has_existence:
            return False
        
        if self.latest_activity_at is None:
            return False
        
        cutoff = _utc_now() - timedelta(days=activity_window_days)
        latest = _ensure_utc_aware(self.latest_activity_at)
        return latest is not None and latest >= cutoff
    
    def is_zombie(self, activity_window_days: int = 90) -> bool:
        """
        Domain-level zombie: has governance + stale/no activity.
        
        INVARIANT: Only domain-canonical assets count as zombie.
        Internal identifiers (name-derived keys) are excluded from zombie counts.
        """
        if not self.is_domain_canonical:
            return False
        
        has_governance = self.has_idp or self.has_cmdb
        
        if not has_governance:
            return False
        
        if self.latest_activity_at is None:
            return True
        
        cutoff = _utc_now() - timedelta(days=activity_window_days)
        latest = _ensure_utc_aware(self.latest_activity_at)
        return latest is not None and latest < cutoff
    
    def get_reason_codes(self) -> list[str]:
        """Generate canonical reason codes for this domain"""
        codes = []
        codes.append("HAS_IDP" if self.has_idp else "NO_IDP")
        codes.append("HAS_CMDB" if self.has_cmdb else "NO_CMDB")
        codes.append("HAS_FINANCE" if self.has_finance else "NO_FINANCE")
        codes.append("HAS_CLOUD" if self.has_cloud else "NO_CLOUD")
        codes.append("HAS_DISCOVERY" if self.has_discovery else "NO_DISCOVERY")
        
        if self.latest_activity_at is not None:
            codes.append("HAS_ACTIVITY_TIMESTAMP")
        else:
            codes.append("NO_ACTIVITY_TIMESTAMP")
        
        if self.is_shadow():
            codes.append("SHADOW_CLASSIFICATION")
        elif self.is_zombie():
            codes.append("ZOMBIE_CLASSIFICATION")
        
        return codes


@dataclass
class DerivedClassificationSummary:
    """Summary of derived classifications for a run"""
    shadow_count: int
    zombie_count: int
    indeterminate_count: int
    shadow_assets: list[dict]
    zombie_assets: list[dict]
    distribution: DistributionDiagnostic = field(default_factory=DistributionDiagnostic)
    domain_rollups: dict[str, DomainRollup] = field(default_factory=dict)


def classify_shadow(asset: Asset, activity_window_days: int = 90) -> ClassificationResult:
    """
    Determine if an asset is a Shadow Asset.
    
    Shadow = has evidence of existence (finance or cloud)
             but is NOT in identity systems and NOT in CMDB
             AND has recent activity within the activity window
    
    Note: Discovery observations are NOT considered for shadow classification
    as they don't represent real-world proof of usage.
    
    Interpretation: "We know this software is used, but it's not being
    managed through official channels."
    
    Uses lens_coverage (boolean flags indicating plane admission) to determine
    presence, not just evidence_refs.
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    has_discovery = asset.lens_coverage.discovery
    
    if has_idp or has_cmdb:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset has IdP or CMDB presence - not shadow",
            evidence_summary=[]
        )
    
    presence_sources = []
    if has_finance:
        presence_sources.append("finance evidence (spending/contracts)")
    if has_cloud:
        presence_sources.append("cloud infrastructure")
    if has_discovery:
        presence_sources.append("discovery (corroborated usage)")
    
    if not presence_sources:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=True,
            classification_type="shadow",
            reason="No evidence of presence - cannot determine shadow status",
            evidence_summary=[]
        )
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    
    if latest_activity is None:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=True,
            classification_type="shadow",
            reason="No activity timestamps available - cannot determine shadow status",
            evidence_summary=[f"Presence: {', '.join(presence_sources)}", "Activity: No timestamps"]
        )
    
    if latest_activity < cutoff_date:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason=f"Activity too old (last seen: {latest_activity.isoformat()}) - outside {activity_window_days} day window",
            evidence_summary=[f"Presence: {', '.join(presence_sources)}", f"Last activity: {latest_activity.isoformat()}"]
        )
    
    gaps = []
    gaps.append("No IdP match (not in SSO/SCIM/identity systems)")
    gaps.append("No CMDB match (not in configuration management)")
    
    return ClassificationResult(
        is_classified=True,
        is_indeterminate=False,
        classification_type="shadow",
        reason=f"Shadow IT: Found via {', '.join(presence_sources)} but missing from official systems",
        evidence_summary=[
            f"Presence: {', '.join(presence_sources)}",
            f"Gaps: {'; '.join(gaps)}",
            f"Last activity: {latest_activity.isoformat()}"
        ]
    )


def compute_zombie_status(asset: Asset, window_days: int = 90) -> tuple[bool, bool, str]:
    """
    Shared zombie status computation used by BOTH KPI counts and debug explainer.
    
    Zombie = (idp_present OR cmdb_present) AND (no timestamps within window)
    If there are NO timestamps at all, that still counts as "no timestamps within window"
    
    Args:
        asset: The asset to check
        window_days: Activity window in days (default 90)
        
    Returns:
        Tuple of (is_zombie, is_indeterminate, reason)
    """
    from datetime import timedelta
    
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    
    if not (has_idp or has_cmdb):
        return False, False, "Not in IdP or CMDB - cannot be zombie"
    
    official_sources = []
    if has_idp:
        official_sources.append("IdP")
    if has_cmdb:
        official_sources.append("CMDB")
    
    latest = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    
    if latest is None:
        return True, False, f"Zombie: In {', '.join(official_sources)} with no activity timestamps"
    
    cutoff = _utc_now() - timedelta(days=window_days)
    
    if latest < cutoff:
        return True, False, f"Zombie: In {', '.join(official_sources)} with stale activity ({latest.isoformat()})"
    
    return False, False, f"Not zombie: Recent activity at {latest.isoformat()}"


def classify_zombie(asset: Asset, activity_window_days: int = 90) -> ClassificationResult:
    """
    Determine if an asset is a Zombie Asset.
    
    Zombie = exists in CMDB or IdP (official records)
             AND (has NO timestamped activity OR activity is outside the window)
    
    Interpretation: "This is in our official systems but we have no
    evidence anyone is actually using it."
    
    IMPORTANT: Activity is determined by timestamps, not evidence_refs.
    If no activity timestamps exist, the asset is classified as zombie
    (we cannot prove it's being used).
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    
    if not (has_idp or has_cmdb):
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason="Asset not in CMDB or IdP - cannot be zombie",
            evidence_summary=[]
        )
    
    official_presence = []
    if has_idp:
        official_presence.append("IdP/identity systems")
    if has_cmdb:
        official_presence.append("CMDB")
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    
    activity_sources = []
    if asset.activity_evidence.discovery_observed_at:
        activity_sources.append("discovery observations")
    if asset.activity_evidence.finance_last_transaction_at:
        activity_sources.append("finance activity")
    if asset.activity_evidence.cloud_observed_at:
        activity_sources.append("cloud activity")
    if asset.activity_evidence.idp_last_login_at:
        activity_sources.append("IdP login")
    if asset.activity_evidence.endpoint_last_seen_at:
        activity_sources.append("endpoint activity")
    if asset.activity_evidence.network_last_seen_at:
        activity_sources.append("network activity")
    
    if latest_activity is None:
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie: Exists in {', '.join(official_presence)} but no activity timestamps to prove usage",
            evidence_summary=[
                f"Official presence: {', '.join(official_presence)}",
                "No timestamped activity evidence"
            ]
        )
    
    if latest_activity < cutoff_date:
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie: Exists in {', '.join(official_presence)} with stale activity (last: {latest_activity.isoformat()}, outside {activity_window_days} day window)",
            evidence_summary=[
                f"Official presence: {', '.join(official_presence)}",
                f"Activity sources: {', '.join(activity_sources)}",
                f"Last activity: {latest_activity.isoformat()} (stale)"
            ]
        )
    
    return ClassificationResult(
        is_classified=False,
        is_indeterminate=False,
        classification_type="zombie",
        reason=f"Asset has recent activity: {', '.join(activity_sources)} (last: {latest_activity.isoformat()})",
        evidence_summary=[f"Last activity: {latest_activity.isoformat()}"]
    )


def compute_derived_classifications(assets: list[Asset], activity_window_days: int = 90) -> DerivedClassificationSummary:
    """
    Compute derived classifications for all assets.
    
    Returns summary with counts and detailed lists.
    
    IMPORTANT: Both counts AND drilldown lists use DOMAIN-AGGREGATED assets.
    This ensures KPI count (16) matches drilldown count (16), not individual
    asset count (49). Multiple assets sharing the same domain are merged.
    
    Note: vendor_hypothesis is included in output dicts for UI DISPLAY ONLY.
    It is NOT used in classification logic.
    Inference decorates reality; it does not redefine it.
    
    Args:
        assets: List of assets to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    distribution = DistributionDiagnostic(total_assets=len(assets))
    
    domain_to_assets: dict[str, list[Asset]] = {}
    
    for asset in assets:
        if asset.lens_status.idp == LensStatus.MATCHED:
            distribution.with_idp_match += 1
        if asset.lens_status.cmdb == LensStatus.MATCHED:
            distribution.with_cmdb_match += 1
        if asset.activity_evidence.latest_activity_at is not None:
            distribution.with_any_activity_timestamp += 1
            latest = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
            if latest is not None and latest > cutoff_date:
                distribution.with_activity_last_30_days += 1
        
        domain_key, _ = _resolve_domain_key(asset)
        if domain_key not in domain_to_assets:
            domain_to_assets[domain_key] = []
        domain_to_assets[domain_key].append(asset)
    
    domain_rollups = compute_domain_rollups(assets, activity_window_days)
    
    shadow_assets = []
    zombie_assets = []
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
                "latest_activity_at": rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else None
            },
            "entity_count": rollup.entity_count,
            "aliases": rollup.entity_names if rollup.entity_count > 1 else [],
            "aggregated_evidence": {
                "has_idp": rollup.has_idp,
                "has_cmdb": rollup.has_cmdb,
                "has_finance": rollup.has_finance,
                "has_cloud": rollup.has_cloud,
                "has_discovery": rollup.has_discovery
            }
        }
        
        if rollup.is_shadow(activity_window_days):
            shadow_assets.append({
                **base_entry,
                "classification": "shadow",
                "reason": f"Shadow IT: {domain_key} found via evidence but missing from official systems",
                "evidence_summary": [
                    f"Presence: {', '.join(filter(None, ['finance' if rollup.has_finance else None, 'cloud' if rollup.has_cloud else None, 'discovery' if rollup.has_discovery else None]))}",
                    "Gaps: No IdP match; No CMDB match",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}"
                ]
            })
        elif rollup.is_zombie(activity_window_days):
            zombie_assets.append({
                **base_entry,
                "classification": "zombie",
                "reason": f"Zombie: {domain_key} in official systems but stale/no activity",
                "evidence_summary": [
                    f"Official presence: {', '.join(filter(None, ['IdP' if rollup.has_idp else None, 'CMDB' if rollup.has_cmdb else None]))}",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'none'}"
                ]
            })
        elif not rollup.is_domain_canonical:
            indeterminate_count += 1
    
    distribution.indeterminate_count = indeterminate_count
    
    return DerivedClassificationSummary(
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        indeterminate_count=indeterminate_count,
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets,
        distribution=distribution,
        domain_rollups=domain_rollups
    )


def _normalize_name_for_vendor_lookup(name: str) -> str:
    """
    Normalize asset name for vendor lookup by stripping common suffixes.
    
    Examples:
        "Notion-prod" -> "notion"
        "Notion (Legacy)" -> "notion"
        "Monday.com-Test" -> "monday.com"
        "Zapier Integration" -> "zapier"
    """
    import re
    name = name.lower().strip()
    name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)
    name = re.sub(r'[-_]\s*(prod|dev|test|staging|legacy|integration|api|v\d+).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(prod|dev|test|staging|legacy|integration|api)$', '', name, flags=re.IGNORECASE)
    return name.strip()


def _resolve_domain_key(asset: Asset) -> tuple[str, bool]:
    """
    Resolve the canonical domain key for an asset.
    
    Returns:
        Tuple of (domain_key, is_canonical) where is_canonical indicates
        whether the key represents a registered domain (True) or is name-derived (False).
    
    Priority order (DOMAIN PROMOTION):
    1. asset.identifiers.domains (explicit domain from evidence) -> canonical
    2. VENDOR_TO_DOMAIN[asset.vendor] (reverse lookup from vendor name) -> canonical
    3. NAME-BASED PROMOTION: Normalize name and look up in VENDOR_TO_DOMAIN -> canonical
    4. Asset name if it looks like a domain -> canonical
    5. Fallback: normalized name -> NOT canonical
    
    INVARIANT: This must match the key resolution in aod_agent_reconcile.py
    to ensure UI counts match reconciliation counts.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return (domain.lower().strip(), True)
    
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return (VENDOR_TO_DOMAIN[vendor_key], True)
    
    normalized_name = _normalize_name_for_vendor_lookup(asset.name)
    if normalized_name in VENDOR_TO_DOMAIN:
        return (VENDOR_TO_DOMAIN[normalized_name], True)
    
    name = asset.name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3) and parts[-1].isalpha():
            return (name, True)
    
    import re
    return (re.sub(r'[^a-z0-9]', '', name.lower()), False)


def compute_domain_rollups(assets: list[Asset], activity_window_days: int = 90) -> dict[str, DomainRollup]:
    """
    Compute domain-level rollups using OR logic across entities.
    
    For reconciliation, governance signals are aggregated at domain level:
    - has_idp = OR(all entities with this domain)
    - has_cmdb = OR(all entities with this domain)
    - etc.
    
    IMPORTANT: HAS_* means PRESENCE (evidence exists), not admission gate passed.
    - has_finance = True if finance correlation found evidence (MATCHED/AMBIGUOUS)
    - has_discovery = True if discovery observations exist (even if stale)
    
    This ensures that if ANY entity under a domain has evidence,
    the domain is considered to have that evidence for reconciliation purposes.
    
    INVARIANT: Domain key resolution matches aod_agent_reconcile.py to ensure
    UI counts match reconciliation counts (eliminating IRL breach).
    """
    rollups: dict[str, DomainRollup] = {}
    
    for asset in assets:
        domain_key, is_canonical = _resolve_domain_key(asset)
        
        has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_finance = asset.lens_status.finance in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_cloud = asset.lens_status.cloud in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_discovery = any(
            isinstance(ref, str) and ref.startswith("discovery:")
            for ref in asset.evidence_refs
        ) or asset.activity_evidence.discovery_observed_at is not None
        latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
        
        if domain_key in rollups:
            r = rollups[domain_key]
            r.has_idp = r.has_idp or has_idp
            r.has_cmdb = r.has_cmdb or has_cmdb
            r.has_finance = r.has_finance or has_finance
            r.has_cloud = r.has_cloud or has_cloud
            r.has_discovery = r.has_discovery or has_discovery
            r.entity_names.append(asset.name)
            r.entity_count += 1
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
                is_domain_canonical=is_canonical
            )
    
    return rollups
