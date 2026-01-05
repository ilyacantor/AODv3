# Late-Binding Domain Merge Implementation Plan

## Problem Statement

**KEY_NORMALIZATION_MISMATCH:** Farm expects domain-based asset keys (e.g., "rapidbox.net") but AOD uses name-based keys (e.g., "RapidBox"). This causes zombie detection failures.

| Metric | Target | Current |
|--------|--------|---------|
| Shadow Accuracy | 100% | 98.2% (56/57) |
| Zombie Accuracy | 100% | 53.6% (30/56) |
| Combined Accuracy | 95%+ | 83% |

**Root Cause:** 26 zombies missed because Farm's ground-truth keys don't match AOD's asset keys.

---

## Solution: Late-Binding Domain Naming + Fan-In Merge

Apply domain-based naming AFTER admission (never mutate entity_id mid-pipeline), then merge assets that share the same registered domain.

### Why Late-Binding?
- Entity IDs must remain stable throughout the pipeline for correlation lookups
- Previous "Domain Primacy" approach failed because it changed entity_id early, breaking lookups
- Late-binding applies transformation only at persistence layer

---

## Implementation Steps

### Step 1: Create Feature Flag

**File:** `src/aod/core/policy/schema.py`

Add to the `Scope` class (or appropriate policy config class):
```python
late_binding_domain_merge: bool = False  # Default OFF for safe rollout
```

### Step 2: Create New Module `asset_identity.py`

**File:** `src/aod/pipeline/asset_identity.py`

```python
"""
Late-binding domain naming and fan-in merge for asset identity resolution.

This module applies domain-based naming AFTER admission to fix KEY_NORMALIZATION_MISMATCH
without mutating entity_id mid-pipeline.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import UUID

from aod.models.asset import (
    Asset,
    AssetIdentifiers,
    ActivityEvidence,
    LensCoverage,
    LensStatus,
    LensStatuses,
)
from aod.utils.domain_utils import extract_registered_domain


def late_bind_and_merge_assets(
    assets: list[Asset],
    feature_enabled: bool,
    logger: Optional[logging.Logger] = None
) -> list[Asset]:
    """
    Apply late-binding domain naming and merge assets by registered domain.
    
    Args:
        assets: List of admitted assets
        feature_enabled: Whether late_binding_domain_merge flag is on
        logger: Optional logger for merge events
        
    Returns:
        List of merged assets (or original list if feature disabled)
    """
    if not feature_enabled:
        return assets
    
    if not assets:
        return assets
    
    # Group assets by merge_key (registered domain)
    groups: dict[str, list[Asset]] = defaultdict(list)
    standalone: list[Asset] = []
    
    for asset in assets:
        merge_key = _compute_merge_key(asset)
        if merge_key:
            groups[merge_key].append(asset)
        else:
            # No domain = standalone, no synthetic merge_key from name
            standalone.append(asset)
    
    # Merge each group
    merged: list[Asset] = []
    for merge_key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            merged_asset = _merge_assets(group, merge_key, logger)
            merged.append(merged_asset)
            if logger:
                logger.info("asset_identity.merge", extra={
                    "merge_key": merge_key,
                    "merged_count": len(group),
                    "merged_asset_ids": [str(a.asset_id) for a in group],
                    "winner_asset_id": str(merged_asset.asset_id)
                })
    
    merged.extend(standalone)
    return merged


def _compute_merge_key(asset: Asset) -> Optional[str]:
    """
    Compute merge key from asset's domains.
    Returns registered domain (eTLD+1) or None if no valid domain.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            registered = extract_registered_domain(domain)
            if registered:
                return registered
    return None


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


def _merge_assets(assets: list[Asset], merge_key: str, logger: Optional[logging.Logger]) -> Asset:
    """
    Merge multiple assets into one using field-by-field merge rules.
    
    Winner selection: lexicographically smallest str(asset.asset_id)
    
    Ordering rules:
    - Domains: [canonical] + winner's domains (in order) + other assets' domains (sorted)
    - Hostnames/URIs/Evidence: winner's first (in order), then others (in encounter order)
    """
    sorted_assets = sorted(assets, key=lambda a: str(a.asset_id))
    winner = sorted_assets[0]
    other_assets = sorted_assets[1:]
    
    # Initialize merged fields
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
    
    # Aggregate from all assets
    for asset in sorted_assets:
        # Lens coverage: OR (union)
        merged_coverage.idp = merged_coverage.idp or asset.lens_coverage.idp
        merged_coverage.cmdb = merged_coverage.cmdb or asset.lens_coverage.cmdb
        merged_coverage.cloud = merged_coverage.cloud or asset.lens_coverage.cloud
        merged_coverage.finance = merged_coverage.finance or asset.lens_coverage.finance
        merged_coverage.discovery = merged_coverage.discovery or asset.lens_coverage.discovery
        
        # Lens status: Precedence (MATCHED > AMBIGUOUS > UNMATCHED)
        merged_status.idp = _precedence_status(merged_status.idp, asset.lens_status.idp)
        merged_status.cmdb = _precedence_status(merged_status.cmdb, asset.lens_status.cmdb)
        merged_status.cloud = _precedence_status(merged_status.cloud, asset.lens_status.cloud)
        merged_status.finance = _precedence_status(merged_status.finance, asset.lens_status.finance)
        
        # Activity timestamps: max()
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
        
        # Track provisioning conflicts
        if asset.provisioning_status != winner.provisioning_status:
            conflicting_statuses.add(asset.provisioning_status)
    
    if conflicting_statuses and logger:
        logger.info("asset_identity.provisioning_conflict", extra={
            "merge_key": merge_key,
            "winner_status": winner.provisioning_status.value,
            "other_statuses": [s.value for s in conflicting_statuses],
            "merged_asset_ids": [str(a.asset_id) for a in sorted_assets]
        })
    
    # Build ordered domains: [canonical] + winner's (in order) + others (sorted)
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
    
    # Build ordered hostnames: winner's first, then others (encounter order)
    hostnames_ordered: list[str] = []
    if winner.identifiers:
        hostnames_ordered.extend(winner.identifiers.hostnames or [])
    for asset in other_assets:
        if asset.identifiers:
            hostnames_ordered.extend(asset.identifiers.hostnames or [])
    deduped_hostnames = _dedupe_preserve_order(hostnames_ordered)
    
    # Build ordered URIs: winner's first, then others (encounter order)
    uris_ordered: list[str] = []
    if winner.identifiers:
        uris_ordered.extend(winner.identifiers.uris or [])
    for asset in other_assets:
        if asset.identifiers:
            uris_ordered.extend(asset.identifiers.uris or [])
    deduped_uris = _dedupe_preserve_order(uris_ordered)
    
    # Build ordered evidence refs: winner's first, then others (encounter order)
    refs_ordered: list[str] = []
    refs_ordered.extend(winner.evidence_refs or [])
    for asset in other_assets:
        refs_ordered.extend(asset.evidence_refs or [])
    deduped_refs = _dedupe_preserve_order(refs_ordered)
    
    # Create merged asset
    merged_asset = Asset(
        asset_id=winner.asset_id,
        tenant_id=winner.tenant_id,
        name=winner.name,
        asset_type=winner.asset_type,
        environment=winner.environment,
        provisioning_status=winner.provisioning_status,
        identifiers=AssetIdentifiers(
            domains=ordered_domains,
            hostnames=deduped_hostnames if deduped_hostnames else None,
            uris=deduped_uris if deduped_uris else None
        ),
        lens_coverage=merged_coverage,
        lens_status=merged_status,
        activity_evidence=merged_activity,
        evidence_refs=deduped_refs if deduped_refs else None
    )
    
    return merged_asset
```

### Step 3: Insert into Pipeline

**File:** `src/aod/pipeline/pipeline_executor.py`

Find the section AFTER admission and BEFORE findings generation. Add:

```python
from aod.pipeline.asset_identity import late_bind_and_merge_assets

# ... inside the pipeline execution, after admission stage ...

# Late-binding domain merge (feature-flagged)
feature_enabled = policy.scope.late_binding_domain_merge if hasattr(policy.scope, 'late_binding_domain_merge') else False
assets = late_bind_and_merge_assets(assets, feature_enabled, logger)

# Continue to findings generation...
```

### Step 4: Update Reconciliation Matching (Optional Enhancement)

**File:** `src/aod/pipeline/derived_classifications.py` and `src/aod/pipeline/aod_agent_reconcile.py`

Update matching logic to match by `asset.name` OR `identifiers.domains` for Farm compatibility:

```python
def matches_ground_truth(asset: Asset, gt_key: str) -> bool:
    """Match asset to ground truth by name or any domain."""
    if asset.name == gt_key:
        return True
    if asset.identifiers and asset.identifiers.domains:
        if gt_key in asset.identifiers.domains:
            return True
    return False
```

---

## Field-by-Field Merge Rules

| Field | Merge Rule |
|-------|-----------|
| asset_id | Winner (lexicographically smallest) |
| tenant_id | Winner |
| name | Winner |
| asset_type | Winner |
| environment | Winner |
| provisioning_status | Winner (log conflicts) |
| identifiers.domains | [canonical] + winner's (in order) + others (sorted) |
| identifiers.hostnames | Winner's (in order) + others (encounter order), deduplicated |
| identifiers.uris | Winner's (in order) + others (encounter order), deduplicated |
| lens_coverage.* | OR (union across all) |
| lens_status.* | Precedence: MATCHED > AMBIGUOUS > UNMATCHED |
| activity_evidence.* | max() of all timestamps |
| evidence_refs | Winner's (in order) + others (encounter order), deduplicated |

---

## No-Domain Fallback Rules

- Assets WITHOUT a registered domain stay standalone
- Do NOT create synthetic merge_key from asset name
- This preserves existing behavior for edge cases

---

## Critical Lessons Learned

### DO NOT
- Change entity_id mid-pipeline (breaks correlation lookups)
- Reject entities without domains (kills zombies)
- Apply alphabetic sorting to hostnames/URIs/evidence (breaks Farm reconciliation)
- Deploy without regression tests

### DO
- Keep entity_id stable throughout pipeline
- Apply identity transformation AFTER admission, before findings
- Preserve winner-first ordering for identifiers and evidence
- Use feature flag for safe rollout (default OFF)
- Test zombie/shadow counts before and after changes

---

## Expected Results

With `late_binding_domain_merge = True`:
- Zombie accuracy: 53.6% → ~100% (26 missed zombies recovered)
- Shadow accuracy: Unchanged (98.2%)
- Combined accuracy: 83% → 95%+

---

## Rollout Plan

1. Implement with feature flag OFF (default)
2. Run regression tests with flag enabled
3. Monitor merge events in staging
4. Enable in production after validation
5. Remove flag once stable

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/aod/core/policy/schema.py` | Add `late_binding_domain_merge: bool = False` |
| `src/aod/pipeline/asset_identity.py` | CREATE - new module |
| `src/aod/pipeline/pipeline_executor.py` | MODIFY - insert merge call after admission |
| `src/aod/pipeline/derived_classifications.py` | MODIFY - update matching logic (optional) |
| `src/aod/pipeline/aod_agent_reconcile.py` | MODIFY - update matching logic (optional) |
| `replit.md` | UPDATE - document new feature |
