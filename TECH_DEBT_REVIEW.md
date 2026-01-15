# AOD Technical Debt Review

**Date:** January 2026
**Scope:** Full codebase review focusing on tech debt, undebuggable logic, janky code, and monoliths

---

## Executive Summary

This codebase implements a sophisticated asset discovery and governance platform with a 7-stage pipeline. While the architecture is sound and the pure function approach to policy evaluation is well-designed, there are significant areas of technical debt that impact maintainability, debuggability, and developer velocity.

**Key Metrics:**
- Pipeline executor: 780 lines
- Admission module: 2,054 lines (largest single file)
- Correlate entities: 1,431 lines
- Database layer: 1,282 lines with significant duplication

---

## ~~CRITICAL: Policy Switchboard Violations~~ ✅ FIXED

**Status: RESOLVED** - All policy values now flow from `config/policy_master.json` via `get_current_config()`.

The following violations were fixed in commit `5434998`:

### Violation Summary

| Module | Hardcoded Value | Should Use |
|--------|-----------------|------------|
| `admission.py:711` | `DISCOVERY_ACTIVITY_WINDOW_DAYS = 90` | `policy_config.activity_windows.discovery_activity_window_days` |
| `admission.py:890` | `MIN_DISCOVERY_SOURCES = 2` | `policy_config.admission_gates.noise_floor` |
| `pipeline_executor.py:35` | `MAX_OBSERVATION_SAMPLES = 2000` | `policy_config.query_limits.max_observation_samples` |
| `pipeline_executor.py:186` | `activity_window_days = 90` | `policy_config.activity_windows.default_activity_window_days` |
| `decision_trace.py:32-43` | `INFRASTRUCTURE_DOMAINS = {...}` | `policy_config.infrastructure_domains` |
| `decision_trace.py:151,188,256` | `window_days: int = 90` | Load from policy |
| `aod_agent_reconcile.py:227,444,717` | `activity_window_days: int = 90` | Load from policy |
| `derived_classifications.py:480` | `window_days: int = 90` | Load from policy |

### Duplicate Domain Lists (3 Copies!)

**INFRASTRUCTURE_DOMAINS is defined in 3 different places:**

1. **`src/aod/constants.py:9-57`** - 57 domains
2. **`src/aod/pipeline/decision_trace.py:32-43`** - 43 domains (DIFFERENT LIST!)
3. **`config/policy_master.json` exclusion_lists.infrastructure_domains** - 19 domains

These lists are **NOT synchronized** and will diverge over time, causing inconsistent behavior.

### Banned/Corporate Domains Bypass Policy

**`admission.py:439-476`** defines local constants that bypass the policy switchboard:

```python
# admission.py - BYPASSES POLICY
BANNED_DOMAINS = {
    "kaspersky.com",
}

CORPORATE_ROOT_DOMAINS = {
    # Placeholder - populated dynamically per tenant if available
}
```

But `policy_master.json` has its own `banned_domains` list with 16 entries including googleapis.com, microsoft.com, etc. **The code ignores the policy file's banned_domains**.

### Deprecated Config Module Still In Use

**`src/aod/config.py`** is marked DEPRECATED but still defines values:

```python
class PolicyConfig:
    """DEPRECATED: Use get_current_config() from aod.core.policy instead."""

    DISCOVERY_ACTIVITY_WINDOW_DAYS: int = 90  # Still used?
    MIN_DISCOVERY_SOURCES_FOR_SHADOW: int = 2  # Conflicts with policy!
    MAX_OBSERVATION_SAMPLES: int = 2000
```

The `policy_master.json` sets `min_discovery_sources_for_shadow: 1` but this deprecated file says `2`.

### Files That Correctly Use Policy

Only **5 out of 29 pipeline files** properly use `get_current_config()`:
- `admission.py` (partial - loads config but also has local constants)
- `correlate_entities.py`
- `derived_classifications.py` (partial)
- `pipeline_executor.py` (partial)
- `api/routes/runs.py`

### Specific Violations

#### 1. `admission.py` - Mixed Usage
```python
# Line 711 - HARDCODED (should come from policy)
DISCOVERY_ACTIVITY_WINDOW_DAYS = 90

# Line 890 - HARDCODED (should come from policy)
MIN_DISCOVERY_SOURCES = 2

# Line 1751 - CORRECTLY loads policy
from aod.core.policy.loader import get_current_config
policy_config = get_current_config()

# But then Line 983 uses the HARDCODED constant, not policy!
cutoff = reference_time - timedelta(days=DISCOVERY_ACTIVITY_WINDOW_DAYS)
```

#### 2. `decision_trace.py` - Completely Ignores Policy
```python
# Line 32-43 - Own copy of INFRASTRUCTURE_DOMAINS (different from constants.py!)
INFRASTRUCTURE_DOMAINS = {
    "redis.io", "redis.com", ...  # 43 domains, not 57
}

# Line 151, 188, 256 - Hardcoded defaults, never loads policy
def _get_activity_info(asset: Asset, window_days: int = 90):
def compute_decision_trace(asset: Asset, activity_window_days: int = 90):
def compute_all_decision_traces(assets: list[Asset], activity_window_days: int = 90):
```

#### 3. `aod_agent_reconcile.py` - Hardcoded Defaults
```python
# Lines 227, 444, 717 - All use hardcoded 90
def emit_actual_results(..., activity_window_days: int = 90, ...):
def build_asset_details(..., activity_window_days: int = 90, ...):
def build_reconciliation_report(..., activity_window_days: int = 90, ...):
```

### Recommended Fix

1. **Remove all module-level policy constants** - Delete `DISCOVERY_ACTIVITY_WINDOW_DAYS`, `MIN_DISCOVERY_SOURCES`, `MAX_OBSERVATION_SAMPLES` from individual files

2. **Single source for domain lists** - Move `INFRASTRUCTURE_DOMAINS` entirely to `policy_master.json` and delete from `constants.py` and `decision_trace.py`

3. **Load policy at function entry** - Replace hardcoded defaults with policy lookups:
```python
# Before (BAD)
def compute_decision_trace(asset: Asset, activity_window_days: int = 90):

# After (GOOD)
def compute_decision_trace(asset: Asset, activity_window_days: int = None):
    if activity_window_days is None:
        policy_config = get_current_config()
        activity_window_days = policy_config.activity_windows.default_activity_window_days
```

4. **Delete deprecated `config.py`** - It's creating confusion with conflicting values

5. **Audit `BANNED_DOMAINS`** - Reconcile the `admission.py` local set with `policy_master.json.exclusion_lists.banned_domains`

---

## Critical Issues (High Priority)

### 1. Monolithic Functions - `admission.py`

**Location:** `src/aod/pipeline/admission.py`

The `apply_admission_criteria()` function is **420+ lines** (lines 1632-2054). This single function handles:
- Domain validation
- Banned domain checks
- Infrastructure domain filtering
- IdP admission
- CMDB admission
- Cloud admission
- Finance admission
- Discovery admission
- Traffic light status calculation
- Lens status computation
- Asset construction

**Impact:**
- Impossible to unit test individual admission criteria
- Any change risks breaking unrelated functionality
- Stack traces are unhelpful (everything points to `apply_admission_criteria`)
- Code review is difficult

**Recommendation:** Break into smaller, composable functions:
```python
# Instead of one giant function:
def apply_admission_criteria(...) -> AdmissionResult:
    # 420+ lines of interleaved logic

# Refactor to:
def validate_domain_gates(domain: str) -> GateResult
def evaluate_governance_admission(correlation) -> AdmissionEvidence
def evaluate_discovery_admission(observations) -> AdmissionEvidence
def compute_traffic_light_status(evidence) -> ProvisioningStatus
def build_admitted_asset(entity, evidence, status) -> Asset
```

---

### 2. ~~Misnomer Field Name - Source vs Plane Count~~ FIXED

**Status:** Renamed `discovery_planes_count` → `discovery_source_count` in all files.

**Files updated:**
- `src/aod/pipeline/pipeline_executor.py:210` - key renamed
- `src/aod/core/policy/engine.py:59,212,265` - docstring and usages updated
- `debug_policy_engine.py:84` - debug output updated
- `debug_production_googleapis_office.py:165` - debug output updated

---

### 3. Excessive Date-Tagged Comments

Throughout the codebase, there are **60+ comments** referencing specific fix dates:
- "Jan 2026 Fix:"
- "Dec 2025 Fix:"
- "Jan 2026 Enhancement:"

**Examples:**
```python
# Jan 2026 Fix: Include vendor-propagated governance AND metadata in policy evaluation.
# Jan 2026 Fix: Governance principle - only AUTHORITATIVE matches can assert governance.
# Dec 2025 Fix: Also check record.domain for domain-based matches
```

**Impact:**
- Code becomes archaeological - readers must understand fix history to understand logic
- Comments explain *when* something was fixed, not *why* the fix was needed
- Makes the code feel patchy rather than coherent

**Recommendation:**
- Remove date prefixes
- Keep only the *why* explanation
- Use git history for *when*

---

### 4. ~~Database Layer Duplication~~ FIXED

**Status:** Extracted `_deserialize_asset_row(row)` helper function.

**Changes:**
- Added `ProvisioningStatus` to top-level imports
- Created `_deserialize_asset_row()` module-level helper
- `get_assets_by_run()` now uses list comprehension with helper
- `get_asset_by_id()` now uses helper directly

---

### 5. ~~Silent Exception Swallowing~~ FIXED

**Status:** Added `logger.debug()` calls for all schema migration exceptions.

**Changes:**
- Added `logging` import and module-level logger
- All 7 schema migration try/except blocks now log exception details at DEBUG level
- Migrations will be visible when DEBUG logging is enabled

---

## Medium Priority Issues

### 6. Correlate Entities - 1,431 Line File

**Location:** `src/aod/pipeline/correlate_entities.py`

This file handles entity correlation across planes with:
- 8 different match strategies
- Multiple disambiguation algorithms
- Pre-computation optimization

The `correlate_to_plane()` function is **613 lines** (572-1185) with deeply nested conditionals.

**Impact:**
- Difficult to understand which match strategy fires
- Testing requires understanding entire flow
- Adding new match strategies is risky

**Recommendation:**
- Extract each match strategy to its own class/function
- Use a strategy pattern for match evaluation
- Make disambiguation a separate, composable module

---

### 7. Magic Numbers

**Location:** Multiple files

```python
# admission.py
DISCOVERY_ACTIVITY_WINDOW_DAYS = 90

# pipeline_executor.py
MAX_OBSERVATION_SAMPLES = 2000

# correlate_entities.py - unlabeled
if len(shorter) < 3:  # What's special about 3?
    return False

if len(canonical) >= 4 and hasattr(plane_index, 'by_name_prefix'):  # Why 4?

if len(shorter) >= 8 and len(shorter) / len(longer) >= 0.7:  # Magic ratio
```

**Recommendation:**
- Move to PolicyConfig or a dedicated constants module
- Document the reasoning behind each threshold

---

### 8. Repeated Domain Extraction Logic

Domain extraction appears in multiple places with slightly different implementations:

| Location | Function |
|----------|----------|
| `admission.py:161-185` | `_clean_url_to_domain()` |
| `admission.py:307-433` | `_extract_domain_from_correlation()` |
| `admission.py:233-304` | `_extract_all_domains_from_correlation()` |
| `normalize_observations.py:46-133` | `resolve_domain_from_observation()` |
| `build_plane_indexes.py` | `_get_raw_domain()` |

**Impact:**
- Domain normalization inconsistencies between modules
- Bugs fixed in one place may not be fixed in others
- Comments explicitly acknowledge duplication: "EXACTLY mirrors the logic in build_plane_indexes"

**Recommendation:** Single source of truth in `domain_cache.py` or a dedicated `domain_normalizer.py`.

---

### 9. Run Route Handler - 809 Lines

**Location:** `src/aod/api/routes/runs.py`

This single route file handles:
- Run creation (3 endpoints)
- Run queries (10+ endpoints)
- Cache management (2 endpoints)
- Classification helpers
- ISO datetime parsing utilities

**Impact:**
- Hard to find specific functionality
- Mixing utility functions with route handlers
- Testing requires mocking entire module

**Recommendation:** Split into:
- `routes/runs/create.py`
- `routes/runs/query.py`
- `routes/runs/cache.py`
- `utils/datetime.py`

---

### 10. Inline Helper Functions

**Location:** `src/aod/pipeline/admission.py`

The `_idp_domain_matches_entity()` function is **115 lines** (1290-1404) with multiple responsibilities:
- Vendor family matching
- TLD-based matching
- Name suffix stripping
- Cross-TLD governance rules

The function contains inline comments like:
```python
# Jan 2026 Fix: Apply the same suffix check as cross-TLD matching
# IdP names with suffixes like "(Legacy)" or "-prod" indicate non-canonical
```

**Impact:**
- Logic is interleaved with comments explaining patches
- Function does too much (3+ responsibilities)
- Nested conditionals 4+ levels deep

---

## Lower Priority Issues

### 11. Inconsistent Logging Patterns

Some modules use structured logging:
```python
logger.info("correlate_entities.complete", extra={"entity_count": len(entities)})
```

Others use f-strings:
```python
logger.warning(f"DOMAIN_EXTRACTION_FAILED entity={entity_key} planes_checked={planes_checked}")
```

**Recommendation:** Standardize on structured logging with `extra={}` dict.

---

### 12. Dead/Deprecated Code

```python
# normalize_observations.py:184
def normalize_name_to_domain(name: str) -> Optional[str]:
    """
    DEPRECATED: Use resolve_domain_from_observation() instead.
    This wrapper is kept for backward compatibility.
    """
```

```python
# normalize_observations.py:225
def normalize_domain(domain: str) -> str:
    """Normalize a domain using IdentityNormalizer.

    DEPRECATED: Use _NORMALIZER.normalize() directly or resolve_domain_from_observation().
    """
```

**Recommendation:** If truly deprecated, remove and update callers. Otherwise, remove "deprecated" label.

---

### 13. Large Constant Dictionaries

**Location:** `src/aod/pipeline/admission.py:713-833`

The `SOURCE_TO_PLANE` dictionary is **120+ entries** inline:

```python
SOURCE_TO_PLANE = {
    "dns": "network",
    "proxy": "network",
    # ... 118 more entries ...
    "synthetic_cloud": "cloud",
}
```

**Recommendation:** Move to a separate `source_mappings.py` or load from config.

---

### 14. Test File Organization

Based on file structure, tests appear minimal:
- `tests/test_aod.py`
- `tests/test_farm_integration.py`
- `tests/test_traffic_light.py`
- `tests/test_canonical_key_equivalence.py`

Given the complexity of the 2000+ line `admission.py`, test coverage appears insufficient.

**Recommendation:** Add unit tests for:
- Each admission check function
- Domain extraction helpers
- Traffic light status computation
- Disambiguation algorithms

---

## Architectural Observations

### What's Working Well

1. **Pure Function Policy Engine** - `engine.py` is clean, stateless, and testable
2. **Data Contracts** - `input_contracts.py` and `output_contracts.py` are well-defined
3. **Async-First Architecture** - Good use of asyncpg and httpx
4. **Deterministic IDs** - `deterministic_ids.py` ensures reproducibility
5. **Hot-Reloadable Policy** - Configuration can change without restart

### Structural Recommendations

1. **Extract Admission Module** - Break `admission.py` into:
   - `admission/gates.py` - Individual admission checks
   - `admission/traffic_light.py` - Status computation
   - `admission/asset_builder.py` - Asset construction
   - `admission/domain_helpers.py` - Domain utilities

2. **Create Domain Service** - Consolidate all domain normalization into one module

3. **Add Integration Tests** - Test pipeline stages end-to-end with fixtures

4. **Schema Migrations** - Replace `try/except pass` with proper migrations (Alembic or similar)

---

## Priority Matrix

| Issue | Severity | Effort | Priority | Status |
|-------|----------|--------|----------|--------|
| ~~Policy switchboard bypasses~~ | ~~Critical~~ | ~~Medium~~ | ~~P0~~ | ✅ FIXED |
| ~~Duplicate INFRASTRUCTURE_DOMAINS~~ | ~~Critical~~ | ~~Low~~ | ~~P0~~ | ✅ FIXED |
| ~~BANNED_DOMAINS ignores policy file~~ | ~~Critical~~ | ~~Low~~ | ~~P0~~ | ✅ FIXED |
| ~~Misnomer field name~~ | ~~High~~ | ~~Low~~ | ~~P1~~ | ✅ FIXED |
| ~~Database duplication~~ | ~~Medium~~ | ~~Low~~ | ~~P2~~ | ✅ FIXED |
| ~~Silent exceptions~~ | ~~Medium~~ | ~~Low~~ | ~~P2~~ | ✅ FIXED |
| Monolithic `apply_admission_criteria` | High | High | P1 | Open |
| Date-tagged comments | Low | Medium | P3 | Open |
| Magic numbers | Low | Low | P3 | Open |
| Route file size | Low | Medium | P3 | Open |

---

## Conclusion

The AOD codebase has a solid architectural foundation with clear separation between pipeline stages and a clean policy engine. However, organic growth has led to several monolithic files (particularly `admission.py`) that require refactoring for long-term maintainability.

The most impactful improvement would be breaking down `apply_admission_criteria()` into composable, testable functions. This would improve debuggability, enable better testing, and make the codebase more approachable for new developers.

Secondary improvements around domain normalization consolidation and database layer cleanup would reduce duplication and prevent inconsistency bugs.
