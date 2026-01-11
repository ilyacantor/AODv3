# Phase 1 Implementation Summary

**Date:** 2026-01-11
**Branch:** claude/analyze-key-normalization-X7VDd
**Commit:** 8fc0112

---

## Problem Solved

**KEY_NORMALIZATION_MISMATCH errors** (~1733 instances across recent assessments)

**Root Cause:** 5 competing domain normalization functions producing divergent canonical keys:
1. `resolve_domain_from_observation()` - Entity creation
2. `_extract_registered_domain()` - Asset reconciliation (with vendor override bug)
3. `_resolve_domain_key()` - Asset classification
4. `_compute_merge_key()` - Late-binding (disabled)
5. `_extract_raw_domain()` - Tracing only

**Baseline Metrics (Before Fix):**
- **Zombie Recall: 67.6%** (needs ≥95%) ❌
- **Shadow Recall: 94.4%** (needs ≥95%) ❌
- Farm expected 109 assets, AOD found 97
- **~1733 KEY_NORMALIZATION_MISMATCH errors**

---

## Solution Implemented

### Created: `src/aod/pipeline/canonical_key.py`

**Single Source of Truth** for domain→key conversion:

```python
def compute_canonical_key(
    domains: list[str],
    vendor: Optional[str] = None,
    name: str = ""
) -> CanonicalKeyResult
```

**Features:**
1. **Unified Normalization Pipeline:**
   - Extract eTLD+1 (registered domain)
   - Check ALIAS_DOMAINS_TO_COLLAPSE
   - Normalize to canonical vendor domain
   - Collect all variants for alias expansion

2. **Consolidated ALIAS_DOMAINS_TO_COLLAPSE:**
   - Added missing aliases: `microsoft365.com`, `dropboxusercontent.io`, `snowflakecomputing.com`
   - Single definition (was duplicated in 2 files)
   - 45 vendor aliases mapped to canonical domains

3. **Fixed Vendor Fallback Bug:**
   - **Before:** Vendor lookup could override explicit domain evidence
   - **After:** Vendor fallback ONLY executes when NO domains exist
   - Example fix: `dropboxusercontent.io` + vendor="Dropbox" → now correctly uses domain, not vendor

---

## Modules Refactored

### 1. `derived_classifications.py`

**Before (92 lines):**
```python
def _resolve_domain_key(asset: Asset) -> tuple[str, bool, list[str]]:
    alias_keys_set = set()
    # ... 90 lines of complex logic
    # Loops through domains
    # Vendor normalization
    # Name-based promotion
    return (primary_key, is_canonical, sorted(alias_keys_set))
```

**After (30 lines):**
```python
def _resolve_domain_key(asset: Asset) -> tuple[str, bool, list[str]]:
    from .canonical_key import compute_canonical_key

    domains = asset.identifiers.domains if asset.identifiers else []
    vendor = asset.vendor if asset.vendor else None
    name = asset.name if asset.name else ""

    result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
    return (result.primary_key, result.is_canonical, result.all_variants)
```

**Changes:**
- `_resolve_domain_key()`: Refactored to use `compute_canonical_key()`
- `_normalize_to_canonical_vendor_domain()`: Now delegates to canonical_key
- `ALIAS_DOMAINS_TO_COLLAPSE`: Imported from canonical_key

---

### 2. `aod_agent_reconcile.py`

**Before (51 lines with vendor override bug):**
```python
def _extract_registered_domain(asset: Asset) -> str | None:
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            # ... domain extraction
            return registered

    # BUG: Vendor fallback can execute even when domains exist!
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]  # ← OVERRIDES domain evidence!
```

**After (13 lines, bug fixed):**
```python
def _extract_registered_domain(asset: Asset) -> str | None:
    from .canonical_key import compute_canonical_key

    domains = asset.identifiers.domains if asset.identifiers else []
    vendor = asset.vendor if asset.vendor else None
    name = asset.name if asset.name else ""

    result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
    return result.primary_key if result.is_canonical else None
```

**Changes:**
- `_extract_registered_domain()`: Refactored to use `compute_canonical_key()` + bug fix
- `_normalize_to_canonical_vendor_domain()`: Now delegates to canonical_key
- `ALIAS_DOMAINS_TO_COLLAPSE`: Imported from canonical_key

---

## Code Reduction

**Lines Removed:** 266
**Lines Added:** 578 (canonical_key.py is comprehensive + docstrings)
**Net Effect:** Duplicate logic eliminated, single source of truth established

**Complexity Reduction:**
- 5 normalization functions → 1 unified function
- 2 ALIAS_DOMAINS_TO_COLLAPSE definitions → 1
- 2 _normalize_to_canonical_vendor_domain() implementations → 1 (+ 2 wrappers)

---

## Expected Impact

### 1. **Eliminate KEY_NORMALIZATION_MISMATCH Errors**

**Before:** Domains exist in AOD evidence but not used as canonical keys
**After:** All domains consistently normalized through single function

**Expected Fix Rate:** ~90-95% of 1733 errors

**Remaining Issues:** May still have ~5-10% due to:
- Missing aliases in ALIAS_DOMAINS_TO_COLLAPSE (can add incrementally)
- Edge cases in TLD parsing (can handle in canonical_key.py)

### 2. **Improve Reconciliation Metrics**

**Baseline (Before):**
- Zombie Recall: 67.6%
- Shadow Recall: 94.4%

**Expected (After):**
- Zombie Recall: **≥95%** ✓
- Shadow Recall: **≥95%** ✓

**Reasoning:**
- Most missed zombies/shadows had KEY_NORMALIZATION_MISMATCH
- Farm expected `microsoft.com`, AOD had `microsoftonline.com`
- Now both use canonical vendor domain consistently

### 3. **Prevent Future Drift**

**Before:** New normalization logic could be added anywhere
**After:** All normalization MUST go through `compute_canonical_key()`

**Enforcement:** Clear docstrings state "this is the ONLY implementation"

---

## Testing Plan

### Step 1: Run Baseline Test
```bash
python run_baseline_test.py
```

**Expected:**
- Reconciliation metrics improve (≥95% recall)
- KEY_NORMALIZATION_MISMATCH count decreases significantly

### Step 2: Run Full Test Suite (if available)
```bash
python -m pytest tests/test_golden_reconciliation.py -v
```

**Acceptance Criteria:**
- Shadow recall ≥95%
- Shadow precision ≥90%
- Zombie recall ≥95%
- Zombie precision ≥90%

### Step 3: Farm Snapshot Comparison
Compare against Farm snapshot: `snapshot-9cc51119-14a2-4013-bae3-b4a4ed68f122`

**Metrics to Track:**
- Number of KEY_NORMALIZATION_MISMATCH errors (should decrease)
- Matched shadows/zombies (should increase)
- False positives (should remain low)

---

## Validation Steps

### ✓ Phase 1 Complete When:
- [x] Single `compute_canonical_key()` function exists
- [x] `_resolve_domain_key()` calls canonical_key
- [x] `_extract_registered_domain()` calls canonical_key
- [x] No duplicate ALIAS_DOMAINS_TO_COLLAPSE definitions
- [x] No duplicate `_normalize_to_canonical_vendor_domain()` implementations
- [x] Vendor fallback bug fixed
- [ ] All existing tests pass
- [ ] Reconciliation metrics ≥95% recall

### Remaining Work:
- [ ] Test against Farm baseline
- [ ] Validate improvements iteratively
- [ ] Add any missing aliases discovered during testing
- [ ] Phase 2: Documentation (if needed)
- [ ] Phase 3: Performance optimization (O(N²) → O(N))

---

## Risk Assessment

### Low Risk ✓
- Changes are **purely consolidation** - same logic, single location
- Backward compatibility maintained (wrappers preserved)
- No policy changes

### Medium Risk ⚠️
- Vendor fallback bug fix might change behavior for edge cases
- ALIAS_DOMAINS_TO_COLLAPSE additions might affect existing assets
- Need to validate no regressions

### Mitigation:
- Comprehensive testing against Farm baseline
- Iterative validation loop
- Can add/remove aliases incrementally if needed

---

## Next Steps

1. **Test Phase 1:**
   ```bash
   python run_baseline_test.py
   ```

2. **If Tests Fail:**
   - Analyze which assets still have KEY_NORMALIZATION_MISMATCH
   - Check if missing aliases in ALIAS_DOMAINS_TO_COLLAPSE
   - Add aliases and re-test iteratively

3. **If Tests Pass:**
   - Document success metrics
   - Consider Phase 2 (documentation) and Phase 3 (performance)

4. **Commit Final Results:**
   - Update KEY_NORMALIZATION_ANALYSIS.md with test results
   - Create summary of improvements

---

## Files Changed

```
modified:   src/aod/pipeline/derived_classifications.py
modified:   src/aod/pipeline/aod_agent_reconcile.py
new file:   src/aod/pipeline/canonical_key.py
new file:   run_baseline_test.py
new file:   PHASE1_IMPLEMENTATION_SUMMARY.md
```

**Total Changes:** +578 -266 lines

---

## Success Criteria

✅ **Phase 1 Success** =
- Reconciliation recall ≥95% (both shadow and zombie)
- KEY_NORMALIZATION_MISMATCH errors reduced by ≥90%
- No false positive increase
- Code consolidation complete (single source of truth)

**Current Status:** Implementation complete, awaiting testing validation
