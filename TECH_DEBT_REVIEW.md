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

### 2. Misnomer Field Name - Source vs Plane Count

**Location:** `src/aod/pipeline/pipeline_executor.py:210`

```python
"discovery_planes_count": len(discovery_sources),  # NOTE: Misnomer - actually source count now
```

**Also at:** `src/aod/core/policy/engine.py:214`
```python
source_count = data.get("discovery_planes_count", 0)  # Misnomer - actually source count
```

**Impact:**
- Future developers will misunderstand the data model
- Policy engine and pipeline use the same misnomer
- Comments explaining the misnomer are scattered across files

**Recommendation:** Rename to `discovery_source_count` with a migration or alias for backward compatibility.

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

### 4. Database Layer Duplication

**Location:** `src/aod/db/database.py`

The `get_assets_by_run()` and `get_asset_by_id()` methods contain **nearly identical** 50-line blocks for deserializing assets:

```python
# Lines 508-549 (get_assets_by_run)
activity_evidence_data = row.get("activity_evidence", "{}")
vendor_hypothesis_data = row.get("vendor_hypothesis")
# ... 40+ lines of deserialization ...

# Lines 564-602 (get_asset_by_id)
activity_evidence_data = row.get("activity_evidence", "{}")
vendor_hypothesis_data = row.get("vendor_hypothesis")
# ... same 40+ lines of deserialization ...
```

**Impact:**
- Any bug fix must be applied twice
- Easy to introduce inconsistencies
- Increases maintenance burden

**Recommendation:** Extract to a `_deserialize_asset_row(row) -> Asset` helper method.

---

### 5. Silent Exception Swallowing

**Location:** `src/aod/db/database.py`

Multiple places silently catch and ignore exceptions:

```python
# Lines 148-190
try:
    await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS vendor_hypothesis TEXT")
except Exception:
    pass  # Silent swallow

try:
    await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS provisioning_status TEXT...")
except Exception:
    pass  # Silent swallow
```

**Impact:**
- Schema migration failures are invisible
- Debugging production issues becomes impossible
- Database could be in inconsistent state

**Recommendation:** At minimum, log the exceptions. Better: use proper migration tooling.

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

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| Monolithic `apply_admission_criteria` | High | High | P1 |
| Misnomer field name | High | Low | P1 |
| Database duplication | Medium | Low | P2 |
| Silent exceptions | Medium | Low | P2 |
| Date-tagged comments | Low | Medium | P3 |
| Magic numbers | Low | Low | P3 |
| Route file size | Low | Medium | P3 |

---

## Conclusion

The AOD codebase has a solid architectural foundation with clear separation between pipeline stages and a clean policy engine. However, organic growth has led to several monolithic files (particularly `admission.py`) that require refactoring for long-term maintainability.

The most impactful improvement would be breaking down `apply_admission_criteria()` into composable, testable functions. This would improve debuggability, enable better testing, and make the codebase more approachable for new developers.

Secondary improvements around domain normalization consolidation and database layer cleanup would reduce duplication and prevent inconsistency bugs.
