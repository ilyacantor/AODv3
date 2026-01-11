# KEY_NORMALIZATION_MISMATCH: Root Cause Analysis & Remediation Plan

**Date:** 2026-01-11
**Branch:** claude/analyze-key-normalization-X7VDd
**Status:** Analysis Complete - NO CODE CHANGES

---

## Executive Summary

The KEY_NORMALIZATION_MISMATCH errors are caused by **5 competing domain normalization functions** that execute at different pipeline stages, each with slightly different logic, producing divergent canonical keys. The codebase has grown organically to include multiple domain resolution paths that were never reconciled into a unified system.

**Critical Finding:** There is no single source of truth for domain-to-key conversion. Each function independently implements normalization rules, leading to scenarios where:
- Entity created with key `microsoftonline.com`
- Asset admitted with domain `login.microsoftonline.com`
- Late-binding normalizes to `microsoftonline.com`
- Classification resolves to `microsoft.com`
- **Farm expects `microsoft.com` but AOD sometimes uses `microsoftonline.com`**

---

## Problem Scope: 5 Competing Normalization Functions

### 1. **`resolve_domain_from_observation()`**
**Location:** `src/aod/pipeline/normalize_observations.py:46-133`
**Purpose:** Entity creation (Stage 2)
**Normalization:** Uses `IdentityNormalizer.normalize()`

**Priority Order:**
1. `obs.domain` → IdentityNormalizer
2. `obs.hostname` → IdentityNormalizer
3. `obs.uri` → IdentityNormalizer
4. `obs.name` (if looks like domain) → IdentityNormalizer
5. `obs.name` → VENDOR_TO_DOMAIN lookup → IdentityNormalizer
6. `obs.vendor` → VENDOR_TO_DOMAIN lookup → IdentityNormalizer

**Characteristics:**
- Delegates all normalization to IdentityNormalizer (black box)
- Creates entity_id = `"entity:{normalized_domain}"`
- This is the FIRST normalization point in the pipeline

---

### 2. **`_extract_raw_domain()`**
**Location:** `src/aod/pipeline/aod_agent_reconcile.py:346-383`
**Purpose:** Asset key extraction (preserves subdomains)
**Normalization:** NONE - returns raw subdomain

**Priority Order:**
1. `asset.identifiers.domains[0]` → lowercase only (NO eTLD+1 normalization)
2. `asset.name` (if looks like domain) → lowercase only
3. `asset.vendor` → VENDOR_TO_DOMAIN lookup

**Characteristics:**
- Intentionally preserves subdomains like `login498.edge.com`
- Comment says: _"matching Farm's host-level granularity"_ ← **THIS IS WRONG!**
- Farm uses **domain-level** keys (eTLD+1), not host-level
- **Used by:** Old code paths (likely legacy, need to confirm if still active)

**CONVOLUTED LOGIC #1:**
This function has the OPPOSITE normalization behavior from all other functions. It's unclear when/if this is still used.

---

### 3. **`_extract_registered_domain()`**
**Location:** `src/aod/pipeline/aod_agent_reconcile.py:464-514`
**Purpose:** Canonical domain extraction with vendor normalization
**Normalization:** eTLD+1 + ALIAS_DOMAINS_TO_COLLAPSE

**Priority Order:**
1. `asset.identifiers.domains[0]` → `extract_registered_domain()` → `_normalize_to_canonical_vendor_domain()`
2. `asset.name` (if looks like domain) → `extract_registered_domain()` → `_normalize_to_canonical_vendor_domain()`
3. `asset.vendor` → VENDOR_TO_DOMAIN lookup ← **CAN OVERRIDE DOMAIN EVIDENCE!**
4. Normalized `asset.name` → VENDOR_TO_DOMAIN lookup

**Characteristics:**
- First extracts eTLD+1 (e.g., `login.microsoftonline.com` → `microsoftonline.com`)
- Then checks if domain is in ALIAS_DOMAINS_TO_COLLAPSE
- If yes, maps to canonical vendor domain (`microsoftonline.com` → `microsoft.com`)
- If no, returns eTLD+1 as-is

**CONVOLUTED LOGIC #2: Vendor Fallback Override**
```python
# Lines 505-508
if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
    vendor_key = asset.vendor.lower().strip()
    if vendor_key in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[vendor_key]  # ← Executes even if domains exist!
```

This should NEVER execute if `identifiers.domains` has values, but it CAN execute if:
- `extract_registered_domain()` returns `None` (TLD parsing failure)
- Falls through to vendor lookup
- Overrides explicit domain evidence with vendor-inferred domain

**Example Bug:**
- Input: `asset.identifiers.domains = ["dropboxusercontent.io"], asset.vendor = "Dropbox"`
- Line 487: `extract_registered_domain("dropboxusercontent.io")` → `None` (unknown TLD)
- Falls through to line 507
- Returns: `VENDOR_TO_DOMAIN["dropbox"]` → `"dropbox.com"`
- **Expected:** `dropboxusercontent.io`
- **Result:** `dropbox.com` ← WRONG!

---

### 4. **`_resolve_domain_key()`**
**Location:** `src/aod/pipeline/derived_classifications.py:911-1002`
**Purpose:** Canonical key for classification + alias expansion
**Normalization:** eTLD+1 + ALIAS_DOMAINS_TO_COLLAPSE + alias_keys collection

**Priority Order:**
1. `asset.identifiers.domains[0]` → `extract_registered_domain()` → `_normalize_to_canonical_vendor_domain()` (PRIMARY KEY)
   - Also processes ALL other domains in `identifiers.domains` to build `alias_keys`
2. `asset.vendor` → VENDOR_TO_DOMAIN lookup
3. Normalized `asset.name` → VENDOR_TO_DOMAIN lookup
4. `asset.name` (if looks like domain) → `extract_registered_domain()` → `_normalize_to_canonical_vendor_domain()`
5. Fallback: sanitized name (NOT canonical)

**Characteristics:**
- **PRIMARY KEY** determined ONLY from `domains[0]` (line 960)
- ALL other domains added to `alias_keys` (lines 946-968)
- Uses SAME alias collapsing logic as `_extract_registered_domain()`
- Returns: `(primary_key, is_canonical, alias_keys)`

**CONVOLUTED LOGIC #3: Primary Key Immutability**
The comment says: _"Primary key is determined from domain[0] only - never changes based on later domains"_

But this creates a problem:
- If `domains[0]` = `"api.slack.com"` (subdomain from discovery)
- And `domains[1]` = `"slack.com"` (from IdP governance)
- Primary key = `slack.com` (from domains[0] after eTLD+1)
- **BUT** if domains were reordered, primary key would be different!

Order matters, but order is non-deterministic (depends on correlation timing).

---

### 5. **`_compute_merge_key()`**
**Location:** `src/aod/pipeline/asset_identity.py:120-152`
**Purpose:** Late-binding domain merge (happens AFTER admission)
**Normalization:** eTLD+1 with SSO/infrastructure deprioritization

**Priority Order:**
1. Scan ALL `asset.identifiers.domains`
2. For each domain: `extract_registered_domain()` → registered domain
3. Prefer first non-SSO, non-infrastructure registered domain
4. Fallback to first valid registered domain (even if SSO/infrastructure)
5. No synthetic merge_key from name (returns None if no domains)

**Characteristics:**
- Scans ALL domains (not just domains[0])
- Deprioritizes SSO domains (okta.com, auth0.com) and infrastructure domains (redis.io, postgresql.org)
- Returns first "real" registered domain
- Used to group assets for merging + normalize singleton domains

**CONVOLUTED LOGIC #4: Late-Binding Timing**
This runs AFTER admission, so:
- Entity created with domain A (from `resolve_domain_from_observation`)
- Asset admitted with identifiers.domains from correlation
- Late-binding prepends merge_key to domains (line 180)
- **But** `classify_actual()` already computed asset_key from original domains!
- Merge_key can DIFFER from asset_key, causing reconciliation mismatch

---

## Problem: Code Duplication

### Duplicate Implementation #1: `_normalize_to_canonical_vendor_domain()`

**Copy 1:** `src/aod/pipeline/aod_agent_reconcile.py:433-461`
**Copy 2:** `src/aod/pipeline/derived_classifications.py:876-908`

Both functions:
- Check if domain is in `ALIAS_DOMAINS_TO_COLLAPSE`
- Look up vendor in `DOMAIN_TO_VENDOR`
- Map to canonical domain via `VENDOR_TO_DOMAIN`

**Risk:** These could drift over time. If one is updated and the other isn't, different modules would have different normalization rules.

---

### Duplicate Implementation #2: `ALIAS_DOMAINS_TO_COLLAPSE`

**Copy 1:** `src/aod/pipeline/aod_agent_reconcile.py:386-430` (45 lines)
**Copy 2:** `src/aod/pipeline/derived_classifications.py` (not shown in reading, but referenced)

Both define the same set of alias domains that should collapse to canonical vendor domains.

---

## Temporal Inconsistency: When Normalization Happens

```
Stage 1: Observations → normalize_observations()
         ↓
   resolve_domain_from_observation()
   Uses IdentityNormalizer.normalize()
   Creates entity_id = "entity:{domain}"

Stage 2: Correlation → admission.py
         ↓
   Entities matched to governance planes
   identifiers.domains populated from correlations
   (Can contain subdomains, registered domains, alias domains)

Stage 3: Admission → Asset objects created
         ↓
   Identifiers.domains = [raw domains from correlation]
   No normalization at this stage

Stage 4: Late-binding → asset_identity.py
         ↓
   _compute_merge_key() normalizes domains
   _normalize_singleton() prepends canonical domain
   Result: domains = ["canonical", "raw1", "raw2", ...]

Stage 5: Classification → aod_agent_reconcile.py
         ↓
   classify_actual() calls _resolve_domain_key()
   Returns (primary_key, is_canonical, alias_keys)
   asset_key = primary_key

Stage 6: Reconciliation → emit_actual_results()
         ↓
   Aggregates assets by asset_key (from classify_actual)
   Expands alias_keys
   Farm matches against shadow_actual/zombie_actual
```

**Problem:** Each stage can produce a DIFFERENT canonical key!

**Example Scenario:**
- **Stage 1:** Entity created with domain `microsoftonline.com`
- **Stage 3:** Asset has `identifiers.domains = ["login.microsoftonline.com"]`
- **Stage 4:** Late-binding prepends `microsoftonline.com` → domains = `["microsoftonline.com", "login.microsoftonline.com"]`
- **Stage 5:** `_resolve_domain_key()` returns `microsoft.com` (alias collapsed)
- **Farm expects:** `microsoft.com`
- **AOD produces:** Depends on which key Farm looks up!
  - If Farm looks up by `microsoftonline.com` → KEY_NORMALIZATION_MISMATCH
  - If Farm looks up by `microsoft.com` → Match ✓

---

## Problem: Multi-Pass Aggregation Complexity

### `emit_actual_results()` - Lines 775-1164 (390 lines!)

This function has **4 distinct passes**, each with different logic:

### Pass 1: Asset-Level Classification (Lines 834-893)
```python
for asset in assets:
    result = classify_actual(asset, ...)
    key = result.asset_key
    # Aggregate into asset_results[key]
```

- Calls `classify_actual()` for each asset
- Uses `_resolve_domain_key()` to get `asset_key`
- Groups assets by `asset_key`
- Tracks: governance, finance, activity per domain

**CONVOLUTED LOGIC #5: Shadow Candidate Tracking**
```python
agg["shadow_candidate_exists"] = agg["shadow_candidate_exists"] or result.is_shadow
```
This tracks if ANY asset under this domain is a shadow candidate. But then...

### Pass 2: Domain-Level Recomputation (Lines 895-971)
```python
for key, agg in asset_results.items():
    # Recompute aggregated activity status
    # Recompute shadow using aggregated governance
    # Recompute zombie with cross-domain suppression
```

Classifications computed in Pass 1 are **OVERRIDDEN** in Pass 2!

**CONVOLUTED LOGIC #6: Cross-Domain Zombie Suppression**
Lines 922-946 implement complex logic:
```python
if not key_lower.endswith('.dev'):
    recent_claimants = []
    has_dev_claimant = False

    for other_key, other_agg in asset_results.items():
        if other_key == key:
            continue
        # Check if OTHER asset claims THIS domain
        other_variants = other_agg.get("all_domain_variants", set())
        if key_lower in other_variants:
            recent_claimants.append(other_key)
            if other_key.endswith('.dev'):
                has_dev_claimant = True

    if len(recent_claimants) >= 2 and has_dev_claimant:
        cross_domain_is_recent = True

# Zombie suppression
agg["is_zombie"] = has_gov_strict and aggregated_is_stale and has_ongoing_finance and not cross_domain_is_recent
```

This is O(N²) complexity! For each asset, iterate through ALL other assets to find "claimants".

**Why is this convoluted?**
1. Nests a double loop (implicit outer, explicit inner)
2. Specific TLD logic (.dev must be present)
3. Requires exactly 2+ claimants (why 2? Magic number)
4. Modifies zombie classification based on OTHER assets' domains

### Pass 3: Output Structure Building (Lines 973-1031)
```python
for key, agg in asset_results.items():
    # Build shadow_actual, zombie_actual, parked_actual lists
    # Build asset_details with evidence_summary
    # Expand alias_keys
```

**CONVOLUTED LOGIC #7: Alias Keys Expansion**
Lines 995-1012:
```python
original_alias_keys = set(evidence.get("alias_keys", []))
all_alias_keys = original_alias_keys.copy()
# Add all domain variants
all_alias_keys.update(domain_aliases)
# Add registered domain
if agg.get("registered_domain"):
    all_alias_keys.add(agg["registered_domain"])
# Remove primary key from aliases
all_alias_keys.discard(key)
alias_keys = sorted(all_alias_keys)

# Update evidence["alias_keys"] so Farm can find it
evidence["alias_keys"] = alias_keys
```

This modifies `evidence_summary` to inject ALL domain variants as alias_keys. But:
- Farm expects alias_keys to enable lookups
- But which aliases should Farm use for matching?
- If Farm looks up by ANY alias, it might find the wrong asset

### Pass 4: Alias Propagation (Lines 1033-1065)
```python
for key, agg in asset_results.items():
    alias_keys = asset_details[key].get("alias_keys", [])
    for alias_domain in alias_keys:
        # Skip if alias is already a primary key for another asset
        if alias_domain in all_primary_keys:
            continue

        # Add alias to classification lists
        if agg["is_shadow"]:
            shadow_actual.append(alias_domain)
```

**CONVOLUTED LOGIC #8: Alias Collision Prevention**
Lines 1055-1056:
```python
if alias_domain in all_primary_keys:
    continue
```

If an alias of Asset A is the primary key of Asset B, DON'T propagate Asset A's classification to that alias.

**Example:**
- Asset A: primary_key = `hipchat.com`, alias_keys = `["atlassian.net"]`, is_zombie = True
- Asset B: primary_key = `atlassian.net`, is_zombie = False
- Without line 1055-1056: `atlassian.net` would appear in zombie_actual (WRONG!)
- With line 1055-1056: Skip `atlassian.net` alias propagation ✓

But this is fragile! It requires tracking `all_primary_keys` and checking every alias. If the check is removed, aliases can override primary keys.

---

## Problem: Governance Strictness Toggle

### Lines 574-593 in `classify_actual()`

```python
has_domain_aligned_idp = (
    has_idp and
    asset.activity_evidence and
    asset.activity_evidence.idp_governance_aligned
)

# For shadow/parked, use broad IdP governance (any match)
# For zombie, use domain-aligned IdP governance only
has_governance_broad = has_idp or has_cmdb
has_governance_strict = has_domain_aligned_idp or has_cmdb
```

**CONVOLUTED LOGIC #9: Governance Means Different Things**

The code defines TWO types of governance:
1. **Broad governance** (`has_idp or has_cmdb`) - used for shadow/parked
2. **Strict governance** (`has_domain_aligned_idp or has_cmdb`) - used for zombie

This means:
- An asset with cross-domain IdP match (name-based, no domain alignment) is:
  - **NOT** a shadow (has_governance_broad = True)
  - **IS** a parked asset (has_governance_strict = False + stale activity)

But the policy docs say: _"Governance = has_idp OR has_cmdb"_

There's a hidden third type of governance (domain-aligned) that's not documented!

**Why is this convoluted?**
- Governance should be a simple boolean: governed or not
- But the code has a spectrum: broad governance vs strict governance
- Classification logic uses DIFFERENT governance definitions
- This violates the "single source of truth" principle

---

## Concrete Bug Scenario

Let's trace a real example through all 5 normalization functions:

### Input
```
Observation:
  observation_id: "obs-123"
  name: "Microsoft Teams"
  domain: "login.microsoftonline.com"
  source: "proxy"

Asset after correlation:
  identifiers.domains: ["login.microsoftonline.com", "teams.microsoft.com"]
  vendor: "Microsoft"
```

### Stage 1: Entity Creation - `resolve_domain_from_observation()`
```python
domain = resolve_domain_from_observation(obs)
# obs.domain = "login.microsoftonline.com"
# IdentityNormalizer.normalize("login.microsoftonline.com")
# Returns: "microsoftonline.com" (eTLD+1)

entity_id = "entity:microsoftonline.com"
```

### Stage 2: Asset Admitted
```python
asset.identifiers.domains = ["login.microsoftonline.com", "teams.microsoft.com"]
# Raw domains preserved
```

### Stage 3: Late-Binding - `_compute_merge_key()`
```python
for domain in ["login.microsoftonline.com", "teams.microsoft.com"]:
    registered = extract_registered_domain(domain)
    # "login.microsoftonline.com" → "microsoftonline.com"
    # "teams.microsoft.com" → "microsoft.com"

    # Check if microsoftonline.com is SSO/infrastructure
    if not _is_sso_or_infrastructure_domain("microsoftonline.com"):
        return "microsoftonline.com"  # First non-SSO domain wins

merge_key = "microsoftonline.com"

# Normalize singleton: prepend merge_key
asset.identifiers.domains = ["microsoftonline.com", "login.microsoftonline.com", "teams.microsoft.com"]
```

### Stage 4: Classification - `_resolve_domain_key()`
```python
# Process domains[0] = "microsoftonline.com"
registered = extract_registered_domain("microsoftonline.com")
# → "microsoftonline.com" (already eTLD+1)

canonical = _normalize_to_canonical_vendor_domain("microsoftonline.com")
# Check: is "microsoftonline.com" in ALIAS_DOMAINS_TO_COLLAPSE?
# Yes! Maps to "microsoft.com"

primary_key = "microsoft.com"
is_canonical = True
alias_keys = ["microsoftonline.com", "login.microsoftonline.com", "teams.microsoft.com"]

return ("microsoft.com", True, alias_keys)
```

### Stage 5: Reconciliation - `emit_actual_results()`
```python
result = classify_actual(asset)
key = result.asset_key  # "microsoft.com"

# Farm lookup:
# Expected: "microsoft.com"
# AOD provides: asset_details["microsoft.com"] = {..., "alias_keys": ["microsoftonline.com", ...]}

# Farm can look up by:
# - "microsoft.com" → FOUND ✓
# - "microsoftonline.com" (from alias_keys) → FOUND ✓
# - "teams.microsoft.com" (from alias_keys) → FOUND ✓
```

### Result: NO MISMATCH (in this scenario)

But if ANY stage returns a DIFFERENT key, mismatch occurs:

### Failure Mode 1: Late-Binding Disabled
If `late_binding_domain_merge = false`:
- asset.identifiers.domains = `["login.microsoftonline.com", "teams.microsoft.com"]`
- `_resolve_domain_key()` processes `domains[0] = "login.microsoftonline.com"`
- registered = `"microsoftonline.com"`, canonical = `"microsoft.com"`
- primary_key = `"microsoft.com"` ✓

Still works! So late-binding doesn't cause this specific mismatch.

### Failure Mode 2: Vendor Fallback Override
If `extract_registered_domain("login.microsoftonline.com")` returns `None`:
```python
# Lines 483-492: domain extraction
registered = extract_registered_domain("login.microsoftonline.com")
if registered:
    # This branch NOT taken (registered = None)
    pass

# Lines 505-508: vendor fallback
if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
    vendor_key = "microsoft"
    if vendor_key in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN["microsoft"]  # → "microsoft.com"
```

So even if TLD parsing fails, vendor fallback correctly returns `"microsoft.com"`.

Still works!

### Failure Mode 3: domains[0] is a Subdomain NOT in ALIAS_DOMAINS_TO_COLLAPSE

```python
asset.identifiers.domains = ["login.microsoft365.com"]  # Not in ALIAS_DOMAINS_TO_COLLAPSE

# _resolve_domain_key()
registered = extract_registered_domain("login.microsoft365.com")
# → "microsoft365.com"

canonical = _normalize_to_canonical_vendor_domain("microsoft365.com")
# Check: is "microsoft365.com" in ALIAS_DOMAINS_TO_COLLAPSE?
# NO! (only "microsoftonline.com", "office365.com" are)

# Returns: "microsoft365.com" (NOT "microsoft.com")
primary_key = "microsoft365.com"
```

**Farm expects:** `microsoft.com`
**AOD produces:** `microsoft365.com`
**Result:** KEY_NORMALIZATION_MISMATCH ❌

**Root Cause:** ALIAS_DOMAINS_TO_COLLAPSE is incomplete!

---

## Summary of Convoluted Logic Patterns

### 1. **Multiple Competing Implementations** (No Single Source of Truth)
- 5 different functions normalize domains
- Each has different priority order and different rules
- No shared canonicalization module

### 2. **Temporal Inconsistency** (Normalization Timing Matters)
- Entity key set in Stage 1
- Asset key set in Stage 5
- Different stages can produce different keys

### 3. **Code Duplication** (DRY Violation)
- `_normalize_to_canonical_vendor_domain()` defined twice
- `ALIAS_DOMAINS_TO_COLLAPSE` defined twice (likely)
- Vendor inference logic scattered across modules

### 4. **Implicit Fallbacks** (Hidden Behavior)
- Vendor fallback can override domain evidence
- Happens when `extract_registered_domain()` returns None
- Not documented in function comments

### 5. **Multi-Pass Aggregation** (Classification Recomputation)
- Classifications computed 4 times
- Each pass can override previous pass
- O(N²) complexity in cross-domain zombie suppression

### 6. **Governance Duality** (Broad vs Strict)
- Two definitions of governance in the same function
- Different classifications use different definitions
- Not aligned with policy documentation

### 7. **Fragile Alias Handling** (Collision Prevention)
- Alias propagation can override primary keys
- Requires explicit collision check
- If check is removed, system breaks

### 8. **Magic Numbers** (Undocumented Thresholds)
- Cross-domain suppression: requires "2+ claimants" (line 943)
- Why 2? Why not 1 or 3?
- Must have ".dev" claimant (line 940)
- Why .dev specifically?

### 9. **Order-Dependent Logic** (Non-Deterministic)
- `_resolve_domain_key()` uses `domains[0]` for primary key
- But domain order depends on correlation timing
- Non-deterministic results if correlation order changes

---

## Remediation Plan (DO NOT IMPLEMENT YET)

### Phase 1: Consolidation (High Priority)

#### 1.1. Create Single Canonical Key Module
**File:** `src/aod/pipeline/canonical_key.py`

```python
def compute_canonical_key(
    domains: list[str],
    vendor: Optional[str],
    name: str
) -> CanonicalKeyResult:
    """
    SINGLE SOURCE OF TRUTH for domain-to-key conversion.

    Returns:
        CanonicalKeyResult with:
        - primary_key: The canonical key to use for reconciliation
        - registered_domain: The eTLD+1 domain
        - all_variants: All domain forms (for alias expansion)
    """
```

**Replaces:**
- `resolve_domain_from_observation()`
- `_extract_registered_domain()`
- `_resolve_domain_key()`
- `_compute_merge_key()`

**CRITICAL:** All 4 functions must call this ONE function.

#### 1.2. Dedup ALIAS_DOMAINS_TO_COLLAPSE
Move to: `src/aod/constants.py`
Delete duplicates in:
- aod_agent_reconcile.py
- derived_classifications.py

#### 1.3. Dedup `_normalize_to_canonical_vendor_domain()`
Move to: `canonical_key.py`
Delete duplicates.

### Phase 2: Simplification (Medium Priority)

#### 2.1. Remove Multi-Pass Aggregation
**Current:** `emit_actual_results()` has 4 passes
**Target:** Single pass with clear classification rules

```python
def emit_actual_results(...):
    # SINGLE PASS: Compute classifications once
    for asset in assets:
        key, is_canonical, alias_keys = compute_canonical_key(...)

        # Compute classification using FINAL aggregated data
        # No recomputation, no overrides
        agg[key] = classify_domain(aggregated_assets[key])
```

#### 2.2. Remove Governance Duality
**Current:** `has_governance_broad` vs `has_governance_strict`
**Target:** Single governance definition

```python
# SINGLE governance definition
has_governance = has_idp or has_cmdb

# If cross-domain IdP matters, handle it separately:
if has_idp_cross_domain_only:
    # Mark as "weak governance" - becomes parked instead of zombie
    pass
```

#### 2.3. Remove `_extract_raw_domain()` (If Unused)
**Check:** Is this function still called anywhere?
**If no:** Delete it (legacy code)
**If yes:** Understand why subdomains are preserved, then refactor

### Phase 3: Performance (Low Priority)

#### 3.1. Remove O(N²) Cross-Domain Zombie Suppression
**Current:** Lines 922-946 in `emit_actual_results()`
**Target:** O(N) using inverted index

```python
# Build domain→assets index once
domain_claimants: dict[str, list[str]] = defaultdict(list)
for key, agg in asset_results.items():
    for variant in agg["all_domain_variants"]:
        domain_claimants[variant].append(key)

# Check claimants in O(1)
claimants = domain_claimants.get(key_lower, [])
has_dev_claimant = any(c.endswith('.dev') for c in claimants)
```

### Phase 4: Testing (Critical)

#### 4.1. Add Property-Based Tests
```python
@given(domain=domain_strategy())
def test_canonical_key_idempotence(domain):
    """Applying canonical key twice should return same result."""
    key1 = compute_canonical_key([domain], None, "")
    key2 = compute_canonical_key([key1.primary_key], None, "")
    assert key1.primary_key == key2.primary_key
```

#### 4.2. Add Integration Tests
Test full pipeline:
```python
def test_end_to_end_key_normalization():
    obs = Observation(domain="login.microsoftonline.com", ...)
    entities = normalize_observations([obs])
    assets = admit_entities(entities, ...)
    results = emit_actual_results("run-123", assets, ...)

    # Farm should be able to look up by ANY variant
    assert "microsoft.com" in results.asset_details
    assert "microsoftonline.com" in results.asset_details["microsoft.com"]["alias_keys"]
```

---

## Risk Assessment

### High Risk Changes
1. Replacing 5 functions with 1 unified function
   - **Risk:** Breaking existing logic that depends on subtle differences
   - **Mitigation:** Comprehensive test coverage before refactor

2. Removing multi-pass aggregation
   - **Risk:** Classifications might change
   - **Mitigation:** Snapshot current output, compare after refactor

### Medium Risk Changes
3. Removing governance duality
   - **Risk:** Zombie counts might change
   - **Mitigation:** Document expected behavior change, validate with Farm

### Low Risk Changes
4. Removing O(N²) logic
   - **Risk:** Behavior change if index has bugs
   - **Mitigation:** Property test: old vs new should return same result

---

## Acceptance Criteria (For Future Implementation)

### Phase 1 Complete When:
- [ ] Single `compute_canonical_key()` function exists
- [ ] All 5 normalization functions call it
- [ ] No duplicate ALIAS_DOMAINS_TO_COLLAPSE definitions
- [ ] No duplicate `_normalize_to_canonical_vendor_domain()` definitions
- [ ] All existing tests pass

### Phase 2 Complete When:
- [ ] `emit_actual_results()` has single pass (no recomputation)
- [ ] Single governance definition across all classification logic
- [ ] `_extract_raw_domain()` removed OR clearly documented why it exists

### Phase 3 Complete When:
- [ ] Cross-domain zombie suppression is O(N)
- [ ] No nested loops in aggregation logic

### Phase 4 Complete When:
- [ ] Property-based tests for canonical key idempotence
- [ ] Integration tests for full pipeline key normalization
- [ ] Baseline reconciliation run matches Farm expectations

---

## Open Questions for Discussion

1. **What is the correct normalization rule?** ✅ **ANSWERED**
   - Should `"login.microsoftonline.com"` → `"microsoft.com"` or `"microsoftonline.com"`?
   - **Farm expects: `microsoft.com` (canonical vendor domain)**
   - AOD currently: Depends on code path (needs consolidation)
   - **Decision: Use ALIAS_DOMAINS_TO_COLLAPSE to map intermediate domains to canonical**

2. **Is `_extract_raw_domain()` still used?**
   - Function preserves subdomains (no normalization)
   - Comment says "matching Farm's host-level granularity"
   - But Farm uses domain-level keys
   - Should this be deleted?

3. **Why does governance have two definitions?**
   - Broad governance for shadow/parked
   - Strict governance for zombie
   - Is this intentional policy or implementation artifact?

4. **Cross-domain zombie suppression: Why .dev TLD?**
   - Line 940: `if other_key.endswith('.dev')`
   - Why is .dev special?
   - What about .app, .io, .tech?

5. **Should late-binding merge be removed?**
   - Currently disabled (was causing issues)
   - Should it be re-enabled after canonical key consolidation?
   - Or permanently removed?

---

## Implementation Guidance (Based on Q1 Answer)

With the confirmed normalization rule (`login.microsoftonline.com` → `microsoft.com`), Phase 1 implementation should:

### 1. Canonical Key Algorithm
```python
def compute_canonical_key(domains: list[str], vendor: Optional[str], name: str) -> CanonicalKeyResult:
    """
    Normalization pipeline:
    1. Extract registered domain (eTLD+1): login.microsoftonline.com → microsoftonline.com
    2. Check ALIAS_DOMAINS_TO_COLLAPSE: microsoftonline.com → microsoft.com
    3. Return canonical vendor domain: microsoft.com

    All variants preserved in alias_keys for Farm lookup.
    """
    if domains:
        raw_domain = domains[0]  # Primary domain
        registered = extract_registered_domain(raw_domain)  # eTLD+1

        # Collapse aliases to canonical
        if registered in ALIAS_DOMAINS_TO_COLLAPSE:
            canonical = DOMAIN_TO_VENDOR[registered] → VENDOR_TO_DOMAIN lookup
            return CanonicalKeyResult(
                primary_key=canonical,  # "microsoft.com"
                registered_domain=registered,  # "microsoftonline.com"
                all_variants=[raw_domain, registered, canonical]  # All forms
            )
```

### 2. ALIAS_DOMAINS_TO_COLLAPSE Completeness
**Action Item:** Audit ALIAS_DOMAINS_TO_COLLAPSE to ensure ALL vendor aliases are included.

Current known gaps (from failure mode #3):
- `microsoft365.com` → Should map to `microsoft.com` (currently missing?)

### 3. Vendor Fallback Fix
Lines 505-508 in `_extract_registered_domain()` should ONLY execute if:
```python
if not domains:  # Only if NO domain evidence exists
    if asset.vendor and asset.vendor in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[asset.vendor]
```

**Do NOT** allow vendor fallback to override domain evidence.

---

## Conclusion

The KEY_NORMALIZATION_MISMATCH issue is not a simple bug - it's an **architectural problem** where multiple domain normalization systems evolved independently and were never unified.

**Root Cause:** No single source of truth for domain→key conversion.

**Solution:** Consolidate all normalization logic into one canonical function, then refactor all call sites to use it.

**Normalization Rule (CONFIRMED):** All domains should normalize to canonical vendor domain (e.g., `microsoft.com`), not intermediate eTLD+1 (`microsoftonline.com`).

**Estimated Effort:**
- Phase 1 (Consolidation): 3-5 days
- Phase 2 (Simplification): 2-3 days
- Phase 3 (Performance): 1-2 days
- Phase 4 (Testing): 2-3 days
- **Total: 8-13 days**

**Recommendation:** Start with Phase 1 (consolidation) as it provides the highest value (fixes KEY_NORMALIZATION_MISMATCH) with manageable risk.

---

**Next Steps:**
1. Review this analysis with team
2. Get stakeholder approval on normalization rules (Question #1)
3. Create detailed implementation spec for Phase 1
4. Implement Phase 1 with comprehensive test coverage
5. Validate against Farm reconciliation baseline
