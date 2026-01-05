"""
Asset Identity - Late-Binding Domain Naming + Fan-In Merge

This module implements the fix for KEY_NORMALIZATION_MISMATCH: Farm expects 
domain-keyed assets, but AOD historically used display names.

The solution applies late-binding domain naming after admission, merging
multiple assets that resolve to the same registered domain.

DESIGN PRINCIPLES:
1. Feature-flagged for safe rollout (default OFF)
2. Deterministic: same inputs -> same outputs
3. Non-destructive: assets without domains pass through unchanged
4. Preserves all evidence via field-by-field merge rules

See CTO_ONBOARDING.md for detailed technical analysis of the mismatch.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from ..models.output_contracts import (
    Asset, AssetIdentifiers, LensStatus, LensStatuses, LensCoverage,
    ActivityEvidence, ProvisioningStatus
)
from .vendor_inference import extract_registered_domain


def _compute_merge_key(asset: Asset) -> Optional[str]:
    """
    Compute the merge key for an asset using domain extraction.
    
    Priority:
    1. asset.identifiers.domains[0] -> extract registered domain
    2. asset.name if domain-like -> extract registered domain
    3. None (asset stays standalone)
    
    Returns the canonical registered domain or None.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                registered = extract_registered_domain(domain)
                if registered:
                    return registered
    
    name = asset.name.lower().strip()
    if "." in name and not name.startswith("."):
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            registered = extract_registered_domain(name)
            if registered:
                return registered
    
    return None


def _max_timestamp(ts1: Optional[datetime], ts2: Optional[datetime]) -> Optional[datetime]:
    """Return the max of two optional timestamps, handling None safely."""
    if ts1 is None:
        return ts2
    if ts2 is None:
        return ts1
    return max(ts1, ts2)


def _precedence_status(s1: LensStatus, s2: LensStatus) -> LensStatus:
    """
    Return higher precedence status.
    
    Precedence: MATCHED > AMBIGUOUS > UNMATCHED
    """
    order = {LensStatus.MATCHED: 3, LensStatus.AMBIGUOUS: 2, LensStatus.UNMATCHED: 1}
    return s1 if order.get(s1, 0) >= order.get(s2, 0) else s2


def _merge_assets(assets: list[Asset], merge_key: str, logger: Optional[logging.Logger]) -> Asset:
    """
    Merge multiple assets into one using field-by-field merge rules.
    
    Winner selection: lexicographically smallest str(asset.asset_id)
    """
    sorted_assets = sorted(assets, key=lambda a: str(a.asset_id))
    winner = sorted_assets[0]
    
    all_domains: list[str] = []
    all_hostnames: list[str] = []
    all_uris: list[str] = []
    all_evidence_refs: list[str] = []
    
    merged_coverage = LensCoverage(
        idp=False,
        cmdb=False,
        cloud=False,
        finance=False,
        discovery=False
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
        if asset.identifiers:
            all_domains.extend(asset.identifiers.domains or [])
            all_hostnames.extend(asset.identifiers.hostnames or [])
            all_uris.extend(asset.identifiers.uris or [])
        
        all_evidence_refs.extend(asset.evidence_refs or [])
        
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
    
    if conflicting_statuses and logger:
        logger.info("asset_identity.provisioning_conflict", extra={
            "merge_key": merge_key,
            "winner_status": winner.provisioning_status.value,
            "other_statuses": [s.value for s in conflicting_statuses],
            "merged_asset_ids": [str(a.asset_id) for a in sorted_assets]
        })
    
    seen_domains = set()
    ordered_domains = [merge_key]
    seen_domains.add(merge_key)
    
    for domain in (winner.identifiers.domains if winner.identifiers else []):
        if domain and domain not in seen_domains:
            ordered_domains.append(domain)
            seen_domains.add(domain)
    
    for domain in sorted(set(all_domains)):
        if domain and domain not in seen_domains:
            ordered_domains.append(domain)
            seen_domains.add(domain)
    
    deduped_hostnames = sorted(set(h for h in all_hostnames if h))
    deduped_uris = sorted(set(u for u in all_uris if u))
    deduped_refs = sorted(set(r for r in all_evidence_refs if r))
    
    merged_asset = Asset(
        asset_id=winner.asset_id,
        tenant_id=winner.tenant_id,
        run_id=winner.run_id,
        name=merge_key,
        asset_type=winner.asset_type,
        identifiers=AssetIdentifiers(
            domains=ordered_domains,
            hostnames=deduped_hostnames,
            uris=deduped_uris
        ),
        vendor=winner.vendor,
        vendor_hypothesis=winner.vendor_hypothesis,
        environment=winner.environment,
        evidence_refs=deduped_refs,
        lens_status=merged_status,
        lens_coverage=merged_coverage,
        lens_match_debug=winner.lens_match_debug,
        activity_evidence=merged_activity,
        tags=winner.tags,
        admission_reason=winner.admission_reason,
        provisioning_status=winner.provisioning_status,
        llm_metadata=winner.llm_metadata,
        has_critical_gap=winner.has_critical_gap,
        owner=winner.owner,
        created_at=winner.created_at
    )
    
    return merged_asset


def late_bind_and_merge_assets(
    assets: list[Asset],
    feature_enabled: bool = False,
    logger: logging.Logger | None = None
) -> list[Asset]:
    """
    Apply late-binding domain naming and fan-in merge to assets.
    
    This is the fix for KEY_NORMALIZATION_MISMATCH: Farm expects domain-keyed assets.
    
    The algorithm:
    1. Short-circuit if feature disabled
    2. Compute merge_key for each asset (registered domain or None)
    3. Group assets by merge_key
    4. For groups with multiple assets: merge using deterministic rules
    5. For standalone assets: pass through unchanged
    6. Return sorted list for determinism
    
    Args:
        assets: List of admitted assets from admission stage
        feature_enabled: Feature flag toggle (default off for safe rollout)
        logger: Logger instance for merge diagnostics
        
    Returns:
        Merged asset list with domain-based naming applied
    """
    if not feature_enabled:
        return assets
    
    if not assets:
        return assets
    
    domain_groups: dict[str, list[Asset]] = defaultdict(list)
    standalone: list[Asset] = []
    
    for asset in assets:
        merge_key = _compute_merge_key(asset)
        if merge_key:
            domain_groups[merge_key].append(asset)
        else:
            standalone.append(asset)
    
    result: list[Asset] = []
    
    for merge_key, group in domain_groups.items():
        if len(group) == 1:
            single_asset = group[0]
            if single_asset.name != merge_key:
                updated = Asset(
                    asset_id=single_asset.asset_id,
                    tenant_id=single_asset.tenant_id,
                    run_id=single_asset.run_id,
                    name=merge_key,
                    asset_type=single_asset.asset_type,
                    identifiers=AssetIdentifiers(
                        domains=[merge_key] + [d for d in (single_asset.identifiers.domains or []) if d != merge_key],
                        hostnames=single_asset.identifiers.hostnames or [],
                        uris=single_asset.identifiers.uris or []
                    ) if single_asset.identifiers else AssetIdentifiers(domains=[merge_key]),
                    vendor=single_asset.vendor,
                    vendor_hypothesis=single_asset.vendor_hypothesis,
                    environment=single_asset.environment,
                    evidence_refs=single_asset.evidence_refs,
                    lens_status=single_asset.lens_status,
                    lens_coverage=single_asset.lens_coverage,
                    lens_match_debug=single_asset.lens_match_debug,
                    activity_evidence=single_asset.activity_evidence,
                    tags=single_asset.tags,
                    admission_reason=single_asset.admission_reason,
                    provisioning_status=single_asset.provisioning_status,
                    llm_metadata=single_asset.llm_metadata,
                    has_critical_gap=single_asset.has_critical_gap,
                    owner=single_asset.owner,
                    created_at=single_asset.created_at
                )
                result.append(updated)
            else:
                result.append(single_asset)
        else:
            merged = _merge_assets(group, merge_key, logger)
            if logger:
                logger.info("asset_identity.merged", extra={
                    "merge_key": merge_key,
                    "merged_count": len(group),
                    "source_ids": [str(a.asset_id) for a in group],
                    "result_id": str(merged.asset_id)
                })
            result.append(merged)
    
    result.extend(standalone)
    
    result.sort(key=lambda a: str(a.asset_id))
    
    return result
