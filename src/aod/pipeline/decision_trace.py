"""
Decision Trace Protocol - Standardized asset decision output for Farm/AOD comparison.

This module produces exactly 13 fields per asset, enabling direct diff between
Farm and AOD to identify whether mismatches are due to:
- Keying (asset_key_used, registered_domain, raw_domains_seen)
- Activity (is_active, activity_window_days, activity_source, latest_activity_at)
- Governance (idp_present, cmdb_present)
- Infra exclusion (infra_excluded, is_external)
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from ..models.output_contracts import Asset, LensStatus
from .vendor_inference import DOMAIN_TO_VENDOR, extract_registered_domain
from ..core.policy import get_current_config


class ActivitySource(str, Enum):
    DNS = "dns"
    PROXY = "proxy"
    BROWSER = "browser"
    ENDPOINT = "endpoint"
    IDP = "idp"
    CLOUD = "cloud"
    FINANCE = "finance"
    NONE = "none"


def _get_infrastructure_domains() -> set[str]:
    """Get infrastructure domains from policy config (single source of truth)."""
    return get_current_config().infrastructure_domains


@dataclass
class DecisionTrace:
    """
    Per-asset decision trace with exactly 13 fields.
    
    This is the minimum protocol to compare Farm and AOD logic comprehensively.
    """
    asset_key_used: str
    registered_domain: Optional[str]
    raw_domains_seen: list[str]
    is_external: bool
    is_active: bool
    activity_window_days: int
    activity_source: ActivitySource
    latest_activity_at: Optional[datetime]
    idp_present: bool
    cmdb_present: bool
    infra_excluded: bool
    is_shadow: bool
    reason_codes: list[str]
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "asset_key_used": self.asset_key_used,
            "registered_domain": self.registered_domain,
            "raw_domains_seen": self.raw_domains_seen[:10],
            "is_external": self.is_external,
            "is_active": self.is_active,
            "activity_window_days": self.activity_window_days,
            "activity_source": self.activity_source.value,
            "latest_activity_at": self.latest_activity_at.isoformat() if self.latest_activity_at else None,
            "idp_present": self.idp_present,
            "cmdb_present": self.cmdb_present,
            "infra_excluded": self.infra_excluded,
            "is_shadow": self.is_shadow,
            "reason_codes": self.reason_codes,
        }


def _extract_raw_domain(asset: Asset) -> Optional[str]:
    """Extract raw domain from asset, preserving subdomains."""
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return domain.lower().strip()
    
    name = asset.name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            return name
    
    return None


def _get_raw_domains(asset: Asset) -> list[str]:
    """Get all raw domains seen for this asset."""
    domains = set()
    if asset.identifiers and asset.identifiers.domains:
        for d in asset.identifiers.domains:
            if d:
                domains.add(d.lower().strip())
    if asset.identifiers and asset.identifiers.hostnames:
        for h in asset.identifiers.hostnames:
            if h:
                domains.add(h.lower().strip())
    return sorted(domains)


def _is_external(asset: Asset) -> bool:
    """Check if asset is external (SaaS/external service vs internal infra)."""
    raw = _extract_raw_domain(asset)
    if not raw:
        return False

    infra_domains = _get_infrastructure_domains()
    registered = extract_registered_domain(raw)
    if registered and registered in infra_domains:
        return False
    if raw in infra_domains:
        return False

    if registered and registered in DOMAIN_TO_VENDOR:
        return True
    if raw in DOMAIN_TO_VENDOR:
        return True

    return True


def _is_infra_excluded(asset: Asset) -> bool:
    """Check if asset is excluded due to being infrastructure."""
    raw = _extract_raw_domain(asset)
    if not raw:
        return False

    infra_domains = _get_infrastructure_domains()
    registered = extract_registered_domain(raw)
    if registered and registered in infra_domains:
        return True
    if raw in infra_domains:
        return True

    return False


def _get_activity_info(asset: Asset, window_days: Optional[int] = None) -> tuple[bool, ActivitySource, Optional[datetime]]:
    """
    Determine activity status, source, and timestamp.

    Returns: (is_active, activity_source, latest_activity_at)
    """
    if window_days is None:
        window_days = get_current_config().activity_windows.default_activity_window_days

    activity = asset.activity_evidence
    if not activity:
        return False, ActivitySource.NONE, None

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    latest: Optional[datetime] = None
    source = ActivitySource.NONE
    
    timestamps = [
        (activity.idp_last_login_at, ActivitySource.IDP),
        (activity.cloud_observed_at, ActivitySource.CLOUD),
        (activity.endpoint_last_seen_at, ActivitySource.ENDPOINT),
        (activity.network_last_seen_at, ActivitySource.PROXY),
        (activity.discovery_observed_at, ActivitySource.BROWSER),
        (activity.finance_last_transaction_at, ActivitySource.FINANCE),
    ]
    
    for ts, src in timestamps:
        if ts:
            ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if latest is None or ts_utc > latest:
                latest = ts_utc
                source = src
    
    if latest is None:
        return False, ActivitySource.NONE, None
    
    is_active = latest >= cutoff
    return is_active, source, latest


def compute_decision_trace(asset: Asset, activity_window_days: Optional[int] = None) -> DecisionTrace:
    """
    Compute the decision trace for a single asset.

    This produces exactly the 13 fields needed to compare Farm and AOD logic.
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    raw_domain = _extract_raw_domain(asset)
    asset_key = raw_domain if raw_domain else asset.name.lower().strip()
    
    registered = extract_registered_domain(raw_domain) if raw_domain else None
    raw_domains = _get_raw_domains(asset)
    
    is_external = _is_external(asset)
    infra_excluded = _is_infra_excluded(asset)
    
    is_active, activity_source, latest_at = _get_activity_info(asset, activity_window_days)
    
    # Use lens_coverage (governance granted) not lens_status (match exists)
    # HAS_CMDB/HAS_IDP mean "passes gates + authoritative match", not "any correlation"
    idp_present = asset.lens_coverage.idp
    cmdb_present = asset.lens_coverage.cmdb
    
    is_shadow = False
    reason_codes = []
    
    if idp_present:
        reason_codes.append("HAS_IDP")
    else:
        reason_codes.append("NO_IDP")
    
    if cmdb_present:
        reason_codes.append("HAS_CMDB")
    else:
        reason_codes.append("NO_CMDB")
    
    if is_active:
        reason_codes.append("RECENT_ACTIVITY")
    else:
        reason_codes.append("STALE_ACTIVITY")
    
    # Source of truth: discovery_sources list (footprint-derived)
    # lens_coverage.discovery is now a derived display, not the truth source
    has_discovery = bool(getattr(asset, "discovery_sources", None))
    if has_discovery:
        reason_codes.append("HAS_DISCOVERY")
    
    if not infra_excluded and is_external:
        if not idp_present and not cmdb_present:
            if is_active and has_discovery:
                is_shadow = True
    
    return DecisionTrace(
        asset_key_used=asset_key,
        registered_domain=registered,
        raw_domains_seen=raw_domains,
        is_external=is_external,
        is_active=is_active,
        activity_window_days=activity_window_days,
        activity_source=activity_source,
        latest_activity_at=latest_at,
        idp_present=idp_present,
        cmdb_present=cmdb_present,
        infra_excluded=infra_excluded,
        is_shadow=is_shadow,
        reason_codes=reason_codes,
    )


def compute_all_decision_traces(assets: list[Asset], activity_window_days: Optional[int] = None) -> list[DecisionTrace]:
    """Compute decision traces for all assets."""
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days
    return [compute_decision_trace(a, activity_window_days) for a in assets]


def decision_traces_to_dict(traces: list[DecisionTrace]) -> dict:
    """Convert list of traces to a dict keyed by asset_key_used."""
    return {t.asset_key_used: t.to_dict() for t in traces}
