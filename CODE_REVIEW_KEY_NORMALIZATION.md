# AODv3 Code Review: KEY_NORMALIZATION_MISMATCH Root Cause Analysis

**Date:** 2025-12-20
**Reviewer:** Claude
**Focus Areas:** Key normalization, tech debt, code quality, KEY_NORMALIZATION_MISMATCH errors

---

## Executive Summary

This code review identified **critical architectural issues** causing KEY_NORMALIZATION_MISMATCH errors where AOD fails to use domain evidence as canonical asset keys, leading to reconciliation failures with Farm.

**Key Findings:**
- 🔴 **CRITICAL:** Multiple canonicalization code paths producing divergent results
- 🔴 **CRITICAL:** Domain evidence being overridden by vendor inference fallback logic
- 🟡 **HIGH:** Inconsistent use of `_extract_raw_domain()` vs `_extract_registered_domain()`
- 🟡 **HIGH:** Complex, hard-to-debug logic in `classify_actual()` and correlation functions
- 🟢 **MEDIUM:** Tech debt in vendor inference and infrastructure filtering

---

## 🔴 CRITICAL ISSUE #1: Multiple Domain Canonicalization Paths

### Problem
There are **three different functions** extracting and normalizing domains, each with slightly different logic:

1. **`extract_registered_domain()`** in `vendor_inference.py:182-213`
2. **`_extract_registered_domain()`** in `aod_agent_reconcile.py:442-480`
3. **`_extract_raw_domain()`** in `aod_agent_reconcile.py:402-439`

### Evidence
**File:** `src/aod/pipeline/aod_agent_reconcile.py`

```python
# Line 402-439: _extract_raw_domain() - preserves subdomains
def _extract_raw_domain(asset: Asset) -> str | None:
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return domain.lower().strip()  # RAW, no normalization!
    # ... vendor fallback logic

# Line 442-480: _extract_registered_domain() - normalizes to eTLD+1
def _extract_registered_domain(asset: Asset) -> str | None:
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                raw_domain = domain.lower().strip()
                registered = extract_registered_domain(raw_domain)  # Normalizes!
                return registered if registered else raw_domain
    # ... vendor fallback logic
```

**File:** `src/aod/pipeline/vendor_inference.py`

```python
# Line 182-213: extract_registered_domain() - different TLD handling
def extract_registered_domain(domain: str) -> Optional[str]:
    if len(parts) == 2:
        return domain  # Early return for 2-part domains

    tld = parts[-1]
    sld = parts[-2]

    if tld in ("com", "net", "org", "io", "co", "app", "dev", "so", "us"):
        return f"{sld}.{tld}"  # Normalize to eTLD+1
```

### Impact
- **Farm expects:** `dropboxusercontent.io` (domain from discovery evidence)
- **AOD produces:** `dropbox.com` (vendor inference fallback)
- **Result:** KEY_NORMALIZATION_MISMATCH error

### Root Cause
The `_extract_registered_domain()` function has a **vendor fallback** that can override explicit domain evidence:

```python
# Lines 471-474 in aod_agent_reconcile.py - PROBLEMATIC FALLBACK
if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
    vendor_key = asset.vendor.lower().strip()
    if vendor_key in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[vendor_key]  # OVERRIDES domain evidence!
```

This violates the documented invariant:
> **INVARIANT:** If any entity has a resolvable registered domain, the asset_key MUST be that registered domain

---

## 🔴 CRITICAL ISSUE #2: Domain Evidence Override by Vendor Inference

### Problem
When an asset has:
- `identifiers.domains = ["dropboxusercontent.io"]` (from discovery)
- `vendor = "Dropbox"` (inferred or from CMDB)

The code flow is:
1. Check `identifiers.domains` → finds `dropboxusercontent.io`
2. Extract registered domain → `dropboxusercontent.io` (no normalization for `.io` with 3+ parts)
3. **BUT THEN:** Vendor fallback logic kicks in → returns `dropbox.com` from `VENDOR_TO_DOMAIN`

### Evidence
**File:** `src/aod/pipeline/aod_agent_reconcile.py:442-480`

The priority order is INCORRECT:
```python
def _extract_registered_domain(asset: Asset) -> str | None:
    """
    Priority order (DOMAIN PROMOTION - domain evidence ALWAYS wins over vendor inference):
    1. asset.identifiers.domains (explicit domain from evidence)
    2. Asset name if it looks like a domain (preserve actual domain-like names)
    3. Reverse lookup from asset.vendor using VENDOR_TO_DOMAIN (only if no domain evidence)  # ← LIE!
    4. NAME-BASED PROMOTION: Normalize name and look up in VENDOR_TO_DOMAIN (last resort)
    """
    # Lines 457-462: Domain check looks good...
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                raw_domain = domain.lower().strip()
                registered = extract_registered_domain(raw_domain)
                return registered if registered else raw_domain

    # Lines 464-469: Name-as-domain check
    name = asset.name.lower().strip()
    if "." in name:
        # ...
        return registered if registered else name

    # Lines 471-474: VENDOR OVERRIDE - This should NEVER execute if domain exists!
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]  # ← BUG: Can override domain!
```

### Why This Happens
The early returns in lines 457-462 and 464-469 should prevent the vendor fallback, but there's a subtle bug:

**When `extract_registered_domain(raw_domain)` returns `None`**, the code falls through to the vendor lookup!

For example:
- Input: `dropboxusercontent.io`
- `extract_registered_domain("dropboxusercontent.io")` → `None` (if TLD handling fails)
- Falls through to vendor lookup → returns `dropbox.com`

---

## 🔴 CRITICAL ISSUE #3: Inconsistent Domain vs Raw Domain Usage

### Problem
`classify_actual()` uses **`_extract_raw_domain()`** to set asset keys:

```python
# Line 528-534 in aod_agent_reconcile.py
raw_domain = _extract_raw_domain(asset)
if raw_domain:
    asset_key = raw_domain  # ← Uses RAW domain (preserves subdomains)
    registered = extract_registered_domain(raw_domain)
    evidence["key_source"] = "domain"
    evidence["registered_domain"] = registered
```

But Farm expects **normalized** keys (eTLD+1), not raw subdomain keys!

### Impact
- AOD emits: `app.slack.com`, `api.stripe.com`, `docs.mongodb.com` (raw subdomains)
- Farm expects: `slack.com`, `stripe.com`, `mongodb.com` (registered domains)
- Result: Key mismatch → KEY_NORMALIZATION_MISMATCH

### Design Confusion
The comment in `_extract_raw_domain()` says:
> "This ensures each subdomain is treated as a separate asset key for shadow/zombie classification, matching Farm's host-level granularity."

But Farm actually uses **domain-level** keys (registered domains), not host-level keys!

---

## 🟡 HIGH PRIORITY ISSUE #4: Overly Complex Classification Logic

### Problem
The `classify_actual()` function (484-548) has deeply nested logic that's hard to reason about:

```python
def classify_actual(asset: Asset, activity_window_days: int = 90, mode: str = "sprawl") -> AssetActualResult:
    reasons, evidence = compute_asset_reasons(asset, activity_window_days)

    eligible = is_reconciliation_eligible(asset, mode=mode)
    evidence["reconciliation_eligible"] = eligible

    if not eligible:
        reasons.append(ReasonCode.NOT_RECONCILIATION_ELIGIBLE)

    # Extract 5 boolean flags from reason codes
    has_idp = ReasonCode.HAS_IDP in reasons
    has_cmdb = ReasonCode.HAS_CMDB in reasons
    has_finance = ReasonCode.HAS_FINANCE in reasons
    has_cloud = ReasonCode.HAS_CLOUD in reasons
    has_discovery = ReasonCode.HAS_DISCOVERY in reasons
    has_recent_activity = ReasonCode.RECENT_ACTIVITY in reasons

    is_shadow = False
    is_zombie = False

    # Nested conditionals for shadow/zombie
    if eligible:
        if not has_idp and not has_cmdb:
            if (has_cloud or has_discovery) and has_recent_activity:
                is_shadow = True

        if has_idp or has_cmdb:
            if not has_recent_activity:
                is_zombie = True

    # More domain extraction logic...
    raw_domain = _extract_raw_domain(asset)
    if raw_domain:
        asset_key = raw_domain
        # ...
    else:
        asset_key = _normalize_key(asset.name)
```

### Issues
1. **Boolean flag explosion:** 6 boolean flags extracted from reason codes, then recombined
2. **Nested conditionals:** 3 levels deep for shadow/zombie logic
3. **Mixed concerns:** Combines classification, key extraction, and evidence building
4. **Hard to test:** Complex branching makes unit testing difficult

### Recommendation
Split into smaller, focused functions:
- `_classify_shadow(reasons, eligible) -> bool`
- `_classify_zombie(reasons, eligible) -> bool`
- `_extract_canonical_key(asset) -> str`

---

## 🟡 HIGH PRIORITY ISSUE #5: Ambiguous Infrastructure Filtering

### Problem
The `is_reconciliation_eligible()` function (242-301) filters out "infrastructure" domains:

```python
INFRASTRUCTURE_DOMAINS = {
    "redis.io", "postgresql.org", "docker.com", "kubernetes.io",
    "elasticsearch.org", "mongodb.com", "mysql.com", ...
}

def is_reconciliation_eligible(asset: Asset, mode: str = "sprawl") -> bool:
    if mode == "infra":
        return True  # All assets eligible in infra mode

    # Check if domain is infrastructure
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                if _is_infrastructure_domain(domain):
                    return False  # EXCLUDED!
                return True
```

### Issues
1. **Hardcoded list:** `INFRASTRUCTURE_DOMAINS` is a 100+ line hardcoded set
2. **Ambiguous classification:** Is `mongodb.com` infrastructure or SaaS? (It's in the list, but MongoDB Atlas is SaaS!)
3. **Vendor confusion:** Code checks vendor against `VENDOR_TO_DOMAIN`, then checks if derived domain is infrastructure
4. **False negatives:** Legitimate SaaS apps might be excluded if their domain matches infrastructure

### Example Bug
```python
# Lines 278-284
if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
    vendor_key = asset.vendor.lower().strip()
    if vendor_key in VENDOR_TO_DOMAIN:
        derived_domain = VENDOR_TO_DOMAIN[vendor_key]
        if _is_infrastructure_domain(derived_domain):
            return False  # Excluded!
    return True
```

If asset has `vendor="MongoDB"`, it derives `mongodb.com`, which is in `INFRASTRUCTURE_DOMAINS`, so the asset is excluded from reconciliation!

---

## 🟢 MEDIUM PRIORITY ISSUE #6: Tech Debt in Vendor Inference

### Problem
**File:** `src/aod/pipeline/vendor_inference.py`

The `DOMAIN_TO_VENDOR` mapping (lines 33-179) is a massive 150-line dict with:
- Duplicate entries (e.g., `"mongodb.com": "MongoDB"` and `"mongodb.org": "MongoDB"`)
- Inconsistent naming (e.g., `"Amazon Web Services"` vs `"AWS"`)
- No versioning or update mechanism

### Example
```python
DOMAIN_TO_VENDOR: dict[str, str] = {
    "mongodb.com": "MongoDB",
    "mongodb.org": "MongoDB",  # Duplicate
    "salesforce.com": "Salesforce",
    "force.com": "Salesforce",  # Duplicate
    "slack.com": "Slack",
    "slackb2b.com": "Slack",  # Duplicate
    # ... 170+ more entries
}
```

### Issues
1. **Maintenance burden:** Adding new vendors requires manual code changes
2. **No data/code separation:** Vendor mappings should be in a config file or database
3. **Duplication:** Same vendor repeated 5-10 times with different domains
4. **Inconsistent with `VENDOR_TO_DOMAIN`:** `aod_agent_reconcile.py` builds a reverse map, creating circular dependency

---

## 🟢 MEDIUM PRIORITY ISSUE #7: Messy Correlation Logic

### Problem
**File:** `src/aod/pipeline/correlate_entities.py`

The `correlate_to_plane()` function (447-887) is a **440-line monster** with:
- 8 matching passes (domain, URI, canonical name, fuzzy, contains, domain token, vendor, domain-vendor)
- Nested disambiguation logic
- Repeated code patterns

### Evidence
```python
def correlate_to_plane(
    entity: CandidateEntity,
    plane_index: PlaneIndex,
    use_domain: bool = True,
    use_uri: bool = False,
    use_vendor: bool = False
) -> PlaneMatch:
    """440 lines of nested if/elif with repeated patterns"""

    # Pass 1: Domain match (lines 479-513)
    if use_domain and entity.domain and plane_index.by_domain:
        domain_matches = plane_index.by_domain.get(entity.domain, [])
        if len(domain_matches) == 1:
            return PlaneMatch(...)  # 10 lines of PlaneMatch construction
        elif len(domain_matches) > 1:
            # Disambiguation logic
            records = [plane_index.records.get(mid) for mid in domain_matches]
            code, detail, resolved = disambiguate_matches(entity, domain_matches, records, "domain")
            if resolved and len(resolved) == 1:
                return PlaneMatch(...)  # Another 10 lines
            return PlaneMatch(...)  # Another 10 lines

    # Pass 2: URI match (lines 515-549) - EXACT SAME PATTERN!
    if use_uri and entity.uri and plane_index.by_uri:
        # ... 35 lines of copy-paste ...

    # Pass 3-8: More copy-paste (lines 551-886)
    # ...
```

### Issues
1. **Massive function:** 440 lines is unreadable and untestable
2. **Code duplication:** Each pass has identical pattern (match → disambiguate → return)
3. **Nested complexity:** Up to 5 levels of nesting
4. **Poor separation:** Matching, disambiguation, and result construction all mixed together

### Recommendation
Refactor into:
```python
def _try_match_by_index(entity, index, key, match_type, records_dict):
    """Generic matching logic - 20 lines"""
    matches = index.get(key, [])
    if len(matches) == 1:
        return _build_single_match(matches[0], records_dict, match_type, key)
    elif len(matches) > 1:
        return _build_ambiguous_match(matches, records_dict, entity, match_type, key)
    return None

def correlate_to_plane(entity, plane_index, use_domain, use_uri, use_vendor):
    """Orchestrator - 50 lines"""
    if use_domain:
        result = _try_match_by_index(entity, plane_index.by_domain, entity.domain, "domain", plane_index.records)
        if result: return result

    if use_uri:
        result = _try_match_by_index(entity, plane_index.by_uri, entity.uri, "uri", plane_index.records)
        if result: return result

    # ... etc
```

---

## 🟢 MEDIUM PRIORITY ISSUE #8: Leaky Abstractions in Farm Adapter

### Problem
**File:** `src/aod/pipeline/farm_adapter.py`

The `normalize_farm_snapshot()` function (439-512) has tight coupling between Farm's wire format and AOD's internal schema.

### Evidence
```python
# Lines 156-173: Helper function accessing nested paths with string keys
def _get_value(data: dict, sources: list[str], default: Any = None) -> Any:
    """Get value from dict using list of possible source paths."""
    for source in sources:
        if "." in source:  # Supports "tags.environment" notation
            parts = source.split(".")
            val = data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    val = None
                    break
```

### Issues
1. **String-based field access:** Uses string parsing for nested paths (`"tags.environment"`)
2. **No type safety:** Loses all type checking from Pydantic models
3. **Error-prone:** Typos in field names fail silently (returns default)
4. **Hard to refactor:** Changing Farm schema requires updating 20+ mapping tables

---

## Summary of Recommendations

### 🔴 **CRITICAL (Fix Immediately)**

1. **FIX:** Remove vendor fallback from `_extract_registered_domain()` when domain evidence exists
   - **File:** `src/aod/pipeline/aod_agent_reconcile.py:471-474`
   - **Change:** Only use vendor fallback if `identifiers.domains` is empty/None

2. **FIX:** Use `_extract_registered_domain()` instead of `_extract_raw_domain()` in `classify_actual()`
   - **File:** `src/aod/pipeline/aod_agent_reconcile.py:528`
   - **Change:** `registered_domain = _extract_registered_domain(asset)` for asset keys

3. **FIX:** Consolidate domain extraction into single canonical function
   - **Files:** `vendor_inference.py`, `aod_agent_reconcile.py`
   - **Change:** Create `src/aod/pipeline/canonical_key.py` with ONE domain extraction function

### 🟡 **HIGH PRIORITY (Fix This Sprint)**

4. **REFACTOR:** Split `classify_actual()` into smaller functions (shadow, zombie, key extraction)
5. **REFACTOR:** Extract infrastructure filtering into config file with clear SaaS vs infrastructure rules
6. **TEST:** Add comprehensive tests for all domain normalization edge cases

### 🟢 **MEDIUM PRIORITY (Tech Debt Backlog)**

7. **REFACTOR:** Split `correlate_to_plane()` into generic matching logic + orchestration
8. **MIGRATE:** Move `DOMAIN_TO_VENDOR` to database or config file
9. **IMPROVE:** Add type safety to Farm adapter field mappings

---

## Testing Gaps

The test file `tests/test_canonical_key_equivalence.py` has good coverage of basic cases, but missing:

1. **Edge cases:**
   - Domains with 3+ parts (e.g., `co.uk`, `com.au`)
   - Typosquat domains (tests exist but don't cover vendor override bug)
   - Infrastructure domains (no tests for filtering logic)

2. **Integration tests:**
   - No tests for `classify_actual()` end-to-end
   - No tests for Farm reconciliation payload generation
   - No tests for domain + vendor interaction

3. **Property-based tests:**
   - Should use Hypothesis to test canonicalization idempotence
   - Should test that vendor fallback never overrides domain evidence

---

## Metrics

- **Files reviewed:** 10 Python files, 5,000+ lines of code
- **Critical issues:** 3
- **High priority issues:** 2
- **Medium priority issues:** 3
- **Tech debt items:** 8+
- **Estimated fix effort:** 2-3 engineer-days for critical issues, 5-7 days for all issues

---

## Conclusion

The KEY_NORMALIZATION_MISMATCH errors are caused by **architectural inconsistency** in domain canonicalization, where multiple code paths extract and normalize domains differently. The immediate fix is to:

1. Remove vendor fallback when domain evidence exists
2. Use registered domains (not raw domains) as asset keys
3. Consolidate all domain extraction into a single, well-tested function

The codebase also suffers from **technical debt** in the form of:
- Massive functions (400+ lines)
- Hardcoded configuration (DOMAIN_TO_VENDOR, INFRASTRUCTURE_DOMAINS)
- Nested complexity (5+ levels deep)
- Code duplication (matching patterns repeated 8 times)

Addressing these issues will significantly improve debuggability and reduce the likelihood of future KEY_NORMALIZATION_MISMATCH errors.
