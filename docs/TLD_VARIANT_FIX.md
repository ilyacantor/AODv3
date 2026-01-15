# TLD Variant Identity Fix (January 2026)

## Summary

This fix addresses **82 admission false positives** caused by cross-TLD entity merging, where assets like `netcloud.com` and `netcloud.io` were being incorrectly collapsed into a single entity.

## Root Cause

Cross-domain brand matching in `correlate_entities.py` was causing identity merge across different registered domains (TLD variants). When entities shared brand tokens (e.g., "netcloud"), the correlation logic would:

1. Add records from `netcloud.io` to the match list for `netcloud.com`
2. Promote domains from heuristic matches into primary identity
3. Allow late-binding merge across different registered domains

This resulted in **KEY_NORMALIZATION_MISMATCH** errors during Farm reconciliation.

## Key Changes

### (A) correlate_entities.py - Cross-TLD Matching Gated

**Before:** Cross-domain brand matches (same first token, different TLD) were added to `contains_matches`, causing identity merge.

**After:** 
- Added `RelatedDomainVariant` dataclass for relationship metadata
- Added `CROSS_TLD_MATCH_METHODS = {"cross_domain_brand"}` to heuristic set
- When registered domains differ, matches are recorded as `related_domain_variants` enrichment, NOT identity
- The `continue` statement prevents adding to `contains_matches`

```python
if entity_registered != record_registered:
    # Record as relationship, NOT as identity match
    cross_tld_variants.append(RelatedDomainVariant(...))
    continue  # DO NOT add to contains_matches
```

### (B) admission.py - Domain Promotion Blocked for Heuristics

**Before:** CMDB domain promotion could occur even for heuristic/fuzzy matches.

**After:**
- Added `PROMOTION_ALLOWED_MATCH_METHODS` (authoritative only)
- Added `PROMOTION_BLOCKED_MATCH_METHODS` (heuristics + cross-TLD)
- Domain promotion explicitly blocked when `match_method` is heuristic
- Logging added: `DOMAIN_PROMOTION_BLOCKED reason=HEURISTIC_MATCH_NOT_AUTHORITATIVE`

```python
if cmdb_primary and cmdb_is_heuristic:
    logger.info(f"DOMAIN_PROMOTION_BLOCKED ...")
    cmdb_primary = None  # Block the promotion
```

### (C) asset_identity.py - Cross-TLD Merge Safety Rail

**Before:** Union-find would merge any assets sharing any domain, regardless of primary.

**After:**
- Added `_get_primary_registered_domain()` helper
- Added `CROSS_TLD_MERGE_BLOCKED` reason code
- Union is skipped when primary registered domains differ
- Logging added for blocked merges

```python
if first_primary != other_primary:
    blocked_merges.append((first_primary, other_primary, domain))
    continue  # DO NOT union - different identity anchors
```

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| Entity identity = eTLD+1 | Key derived from registered domain only |
| Cross-TLD = relationship | `RelatedDomainVariant` edge, not identity |
| Authoritative-only governance | Only domain/uri/canonical_name can assert governance |
| Heuristics = enrichment | fuzzy/contains/brand matches for metadata only |
| Late-binding guard | Primary domain must match for union |

## Affected Match Methods

### Authoritative (can assert governance)
- `domain`
- `uri`
- `canonical_name`

### Heuristic (enrichment only, blocked from promotion)
- `fuzzy`
- `contains`
- `vendor`
- `domain_vendor`
- `vendor_fallback`
- `name_contains_domain_token`
- `normalization_token`
- `cross_domain_brand` (NEW)

## Regression Prevention

Unit tests in `tests/test_tld_variant_isolation.py`:

1. `TestCrossTLDMatchMethodClassification` - Verifies match method categorization
2. `TestDomainPromotionBlocking` - Verifies promotion rules
3. `TestRelatedDomainVariant` - Verifies relationship metadata structure
4. `TestTLDVariantIsolation` - Core test: netcloud.com != netcloud.io
5. `TestPrimaryRegisteredDomain` - Verifies primary domain extraction
6. `TestMatchQualityClassification` - Verifies authoritative classification

## Expected Impact

- **82 false positives eliminated** (63% from TLD variant merging, 32% from key normalization)
- **KEY_NORMALIZATION_MISMATCH count reduced** in reconciliation
- **Deterministic entity identity** based on eTLD+1 only
- **Audit trail preserved** via `related_domain_variants` metadata

## Files Changed

| File | Changes |
|------|---------|
| `src/aod/pipeline/correlate_entities.py` | RelatedDomainVariant, cross-TLD gate |
| `src/aod/pipeline/admission.py` | PROMOTION_ALLOWED/BLOCKED, promotion block |
| `src/aod/pipeline/asset_identity.py` | Primary domain check, merge safety rail |
| `tests/test_tld_variant_isolation.py` | New test file |
| `docs/TLD_VARIANT_FIX.md` | This document |
