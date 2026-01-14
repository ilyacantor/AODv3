"""
Late-binding domain naming and fan-in merge for asset identity resolution.

This module applies domain-based naming AFTER admission to fix KEY_NORMALIZATION_MISMATCH
without mutating entity_id mid-pipeline.

INVARIANT: Entity IDs remain stable throughout the pipeline.
Transformation is applied only at the persistence layer (late-binding).

Design:
1. Group assets by registered domain (merge_key)
2. Merge assets with same merge_key using field-by-field rules
3. Preserve winner-first ordering for determinism
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from ..models.output_contracts import (
    Asset,
    AssetIdentifiers,
    ActivityEvidence,
    LensCoverage,
    LensStatus,
    LensStatuses,
)
from ..constants import INFRASTRUCTURE_DOMAINS
from .vendor_inference import extract_registered_domain

logger = logging.getLogger(__name__)


SSO_PROVIDER_DOMAINS: set[str] = {
    "okta.com", "oktapreview.com",
    "auth0.com",
    "onelogin.com",
    "pingidentity.com", "pingone.com",
    "duo.com", "duosecurity.com",
    "jumpcloud.com",
}

def _is_sso_or_infrastructure_domain(domain: str) -> bool:
    """Check if domain is an SSO provider or infrastructure domain that should be deprioritized."""
    return domain in SSO_PROVIDER_DOMAINS or domain in INFRASTRUCTURE_DOMAINS


def late_bind_and_merge_assets(
    assets: list[Asset],
    feature_enabled: bool,
    run_logger: Optional[logging.Logger] = None
) -> list[Asset]:
    """
    Apply late-binding domain naming and merge assets by registered domain.
    
    Args:
        assets: List of admitted assets
        feature_enabled: Whether late_binding_domain_merge flag is on
        run_logger: Optional logger for merge events
        
    Returns:
        List of merged assets (or original list if feature disabled)
    """
    if not feature_enabled:
        return assets
    
    if not assets:
        return assets
    
    log = run_logger or logger
    
    groups: dict[str, list[Asset]] = defaultdict(list)
    standalone: list[Asset] = []
    
    for asset in assets:
        merge_key = _compute_merge_key(asset)
        if merge_key:
            groups[merge_key].append(asset)
        else:
            standalone.append(asset)
    
    merged: list[Asset] = []
    merge_count = 0
    normalized_count = 0
    
    for merge_key, group in groups.items():
        if len(group) == 1:
            original = group[0]
            normalized_asset = _normalize_singleton(original, merge_key, log)
            original_first = original.identifiers.domains[0] if original.identifiers and original.identifiers.domains else None
            if original_first != merge_key:
                normalized_count += 1
            merged.append(normalized_asset)
        else:
            merged_asset = _merge_assets(group, merge_key, log)
            merged.append(merged_asset)
            merge_count += 1
            log.info("asset_identity.merge", extra={
                "merge_key": merge_key,
                "merged_count": len(group),
                "merged_asset_ids": [str(a.asset_id) for a in group],
                "winner_asset_id": str(merged_asset.asset_id)
            })
    
    merged.extend(standalone)
    
    if merge_count > 0 or normalized_count > 0:
        log.info("asset_identity.summary", extra={
            "input_assets": len(assets),
            "output_assets": len(merged),
            "merges_performed": merge_count,
            "singletons_normalized": normalized_count,
            "standalone_assets": len(standalone)
        })
    
    return merged


def _compute_merge_key(asset: Asset) -> Optional[str]:
    """
    Compute merge key from asset's domains.
    Returns registered domain (eTLD+1) or None if no valid domain.
    
    Scans ALL domains and prefers non-SSO/non-infrastructure domains.
    Does NOT create synthetic merge_key from asset name.
    Assets without domains stay standalone.
    
    Priority:
    1. First non-SSO, non-infrastructure registered domain
    2. Fallback to first valid registered domain if all are SSO/infrastructure
    """
    if not asset.identifiers or not asset.identifiers.domains:
        return None
    
    first_registered: Optional[str] = None
    
    for domain in asset.identifiers.domains:
        if not domain:
            continue
        
        registered = extract_registered_domain(domain)
        if not registered:
            continue
        
        if first_registered is None:
            first_registered = registered
        
        if not _is_sso_or_infrastructure_domain(registered):
            return registered
    
    return first_registered


def _normalize_singleton(asset: Asset, merge_key: str, log: logging.Logger) -> Asset:
    """
    Normalize a singleton asset by ensuring canonical domain is first.
    
    This fixes KEY_NORMALIZATION_MISMATCH for single assets by:
    1. Prepending the canonical registered domain to identifiers.domains
    2. Ensuring Farm can match on the canonical domain
    
    Returns a new Asset if normalization was needed, otherwise the original.
    Uses model_copy() to preserve all fields without explicit enumeration.
    """
    current_domains = asset.identifiers.domains if asset.identifiers else []
    
    if current_domains and current_domains[0] == merge_key:
        return asset
    
    seen: set[str] = set()
    ordered_domains: list[str] = [merge_key]
    seen.add(merge_key)
    
    for domain in current_domains:
        if domain and domain not in seen:
            ordered_domains.append(domain)
            seen.add(domain)
    
    new_identifiers = asset.identifiers.model_copy(update={"domains": ordered_domains}) if asset.identifiers else AssetIdentifiers(domains=ordered_domains)
    normalized_asset = asset.model_copy(update={"identifiers": new_identifiers})
    
    log.debug("asset_identity.singleton_normalized", extra={
        "asset_id": str(asset.asset_id),
        "merge_key": merge_key,
        "original_first_domain": current_domains[0] if current_domains else None,
        "new_domains": ordered_domains[:3]
    })
    
    return normalized_asset


def _max_timestamp(t1: Optional[datetime], t2: Optional[datetime]) -> Optional[datetime]:
    """Return the more recent of two timestamps."""
    if t1 is None:
        return t2
    if t2 is None:
        return t1
    return max(t1, t2)


def _precedence_status(s1: LensStatus, s2: LensStatus) -> LensStatus:
    """Return higher precedence status: MATCHED > AMBIGUOUS > UNMATCHED."""
    order = {LensStatus.MATCHED: 3, LensStatus.AMBIGUOUS: 2, LensStatus.UNMATCHED: 1}
    return s1 if order.get(s1, 0) >= order.get(s2, 0) else s2


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate list while preserving encounter order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_assets(assets: list[Asset], merge_key: str, log: logging.Logger) -> Asset:
    """
    Merge multiple assets into one using field-by-field merge rules.
    
    Winner selection: lexicographically smallest str(asset.asset_id)
    
    Ordering rules:
    - Domains: [canonical] + winner's domains (in order) + other assets' domains (sorted)
    - Hostnames/URIs/Evidence: winner's first (in order), then others (in encounter order)
    
    Merge rules:
    - lens_coverage.*: OR (union across all)
    - lens_status.*: Precedence (MATCHED > AMBIGUOUS > UNMATCHED)
    - activity_evidence.*: max() of all timestamps
    - evidence_refs: Winner's first, then others (deduplicated)
    """
    sorted_assets = sorted(assets, key=lambda a: str(a.asset_id))
    winner = sorted_assets[0]
    other_assets = sorted_assets[1:]
    
    merged_coverage = LensCoverage(
        idp=False, cmdb=False, cloud=False, finance=False, discovery=False
    )
    
    merged_status = LensStatuses(
        idp=LensStatus.UNMATCHED,
        cmdb=LensStatus.UNMATCHED,
        cloud=LensStatus.UNMATCHED,
        finance=LensStatus.UNMATCHED
    )
    
    merged_activity = ActivityEvidence(
        idp_last_login_at=None,
        discovery_observed_at=None,
        cloud_observed_at=None,
        endpoint_last_seen_at=None,
        network_last_seen_at=None,
        finance_last_transaction_at=None,
        latest_activity_at=None
    )
    
    conflicting_statuses = set()
    
    for asset in sorted_assets:
        merged_coverage.idp = merged_coverage.idp or asset.lens_coverage.idp
        merged_coverage.cmdb = merged_coverage.cmdb or asset.lens_coverage.cmdb
        merged_coverage.cloud = merged_coverage.cloud or asset.lens_coverage.cloud
        merged_coverage.finance = merged_coverage.finance or asset.lens_coverage.finance
        merged_coverage.discovery = merged_coverage.discovery or asset.lens_coverage.discovery
        
        merged_status.idp = _precedence_status(merged_status.idp, asset.lens_status.idp)
        merged_status.cmdb = _precedence_status(merged_status.cmdb, asset.lens_status.cmdb)
        merged_status.cloud = _precedence_status(merged_status.cloud, asset.lens_status.cloud)
        merged_status.finance = _precedence_status(merged_status.finance, asset.lens_status.finance)
        
        merged_activity.idp_last_login_at = _max_timestamp(
            merged_activity.idp_last_login_at, asset.activity_evidence.idp_last_login_at
        )
        merged_activity.discovery_observed_at = _max_timestamp(
            merged_activity.discovery_observed_at, asset.activity_evidence.discovery_observed_at
        )
        merged_activity.cloud_observed_at = _max_timestamp(
            merged_activity.cloud_observed_at, asset.activity_evidence.cloud_observed_at
        )
        merged_activity.endpoint_last_seen_at = _max_timestamp(
            merged_activity.endpoint_last_seen_at, asset.activity_evidence.endpoint_last_seen_at
        )
        merged_activity.network_last_seen_at = _max_timestamp(
            merged_activity.network_last_seen_at, asset.activity_evidence.network_last_seen_at
        )
        merged_activity.finance_last_transaction_at = _max_timestamp(
            merged_activity.finance_last_transaction_at, asset.activity_evidence.finance_last_transaction_at
        )
        merged_activity.latest_activity_at = _max_timestamp(
            merged_activity.latest_activity_at, asset.activity_evidence.latest_activity_at
        )
        
        if asset.provisioning_status != winner.provisioning_status:
            conflicting_statuses.add(asset.provisioning_status)
    
    if conflicting_statuses:
        log.info("asset_identity.provisioning_conflict", extra={
            "merge_key": merge_key,
            "winner_status": winner.provisioning_status.value,
            "other_statuses": [s.value for s in conflicting_statuses],
            "merged_asset_ids": [str(a.asset_id) for a in sorted_assets]
        })
    
    seen_domains: set[str] = set()
    ordered_domains: list[str] = [merge_key]
    seen_domains.add(merge_key)
    
    for domain in (winner.identifiers.domains if winner.identifiers else []):
        if domain and domain not in seen_domains:
            ordered_domains.append(domain)
            seen_domains.add(domain)
    
    other_domains: list[str] = []
    for asset in other_assets:
        if asset.identifiers:
            for domain in (asset.identifiers.domains or []):
                if domain and domain not in seen_domains:
                    other_domains.append(domain)
                    seen_domains.add(domain)
    for domain in sorted(other_domains):
        ordered_domains.append(domain)
    
    hostnames_ordered: list[str] = []
    if winner.identifiers:
        hostnames_ordered.extend(winner.identifiers.hostnames or [])
    for asset in other_assets:
        if asset.identifiers:
            hostnames_ordered.extend(asset.identifiers.hostnames or [])
    deduped_hostnames = _dedupe_preserve_order(hostnames_ordered)
    
    uris_ordered: list[str] = []
    if winner.identifiers:
        uris_ordered.extend(winner.identifiers.uris or [])
    for asset in other_assets:
        if asset.identifiers:
            uris_ordered.extend(asset.identifiers.uris or [])
    deduped_uris = _dedupe_preserve_order(uris_ordered)
    
    refs_ordered: list[str] = []
    refs_ordered.extend(winner.evidence_refs or [])
    for asset in other_assets:
        refs_ordered.extend(asset.evidence_refs or [])
    deduped_refs = _dedupe_preserve_order(refs_ordered)
    
    merged_tags: list[str] = []
    merged_tags.extend(winner.tags or [])
    for asset in other_assets:
        for tag in (asset.tags or []):
            if tag not in merged_tags:
                merged_tags.append(tag)
    
    merged_asset = Asset(
        asset_id=winner.asset_id,
        tenant_id=winner.tenant_id,
        run_id=winner.run_id,
        name=winner.name,
        asset_type=winner.asset_type,
        environment=winner.environment,
        vendor=winner.vendor,
        vendor_hypothesis=winner.vendor_hypothesis,
        provisioning_status=winner.provisioning_status,
        identifiers=AssetIdentifiers(
            domains=ordered_domains,
            hostnames=deduped_hostnames if deduped_hostnames else [],
            uris=deduped_uris if deduped_uris else []
        ),
        lens_coverage=merged_coverage,
        lens_status=merged_status,
        lens_match_debug=winner.lens_match_debug,
        activity_evidence=merged_activity,
        evidence_refs=deduped_refs if deduped_refs else [],
        tags=merged_tags,
        admission_reason=winner.admission_reason
    )
    
    return merged_asset
