# AOD Code Review - January 2026

**Reviewer:** Claude Code
**Date:** 2026-01-17
**Branch:** claude/aod-code-review-s11qH
**Status:** PROPOSAL ONLY - No code changes made

---

## Executive Summary

AODv3 is a well-architected, production-ready enterprise asset discovery platform with a 98.7% reconciliation accuracy rate. The codebase demonstrates strong engineering principles including deterministic processing, evidence-based decisions, and comprehensive testing (18 test files).

This review identifies opportunities for improvement across architecture, performance, maintainability, and security.

---

## CRITICAL: Shared Dev/Prod Database Safeguards

**Concern Raised:** Dev and production share a single database.

### Current State Analysis

| Aspect | Status | Risk Level |
|--------|--------|------------|
| Database URL Configuration | Single env var (`SUPABASE_DB_URL` or `DATABASE_URL`) | **HIGH** |
| Environment Detection | **None** - no `ENV`, `NODE_ENV`, or `APP_ENV` checking | **HIGH** |
| Authentication | **None** - no API keys, tokens, or auth middleware | **CRITICAL** |
| Destructive Endpoints | Unprotected `DELETE /api/runs` wipes ALL data | **CRITICAL** |
| CORS Policy | Wildcard `allow_origins=["*"]` | **HIGH** |
| Tenant Isolation | Data scoped by `tenant_id`, but no access control | **MEDIUM** |
| Rate Limiting | **None** | **MEDIUM** |

### Safeguards Currently in Place

1. **Run Isolation**: All assets/findings/artifacts are scoped to `run_id` - queries always filter by run
2. **Tenant ID Scoping**: Data includes `tenant_id` for logical separation
3. **Foreign Key Constraints**: Assets reference runs, preventing orphaned data
4. **No Cascade Deletes**: Deleting a run requires explicit deletion of child tables first

### Safeguards MISSING (Proposals)

#### C1: CRITICAL - Add Environment Guard for Destructive Operations

**Location:** `api/routes/runs.py:350-360`

**Current Code (DANGEROUS):**
```python
@router.delete("")
async def delete_all_runs():
    """Delete all discovery runs and associated data"""
    db = await get_db_direct()
    deleted = await db.delete_all_runs()
    return {"message": f"Deleted {deleted} runs..."}
```

**Issue:** No confirmation, no environment check, no audit trail. One API call wipes everything.

**Proposal:**
```python
import os

@router.delete("")
async def delete_all_runs(confirm: str = Query(..., description="Must be 'DELETE_ALL_CONFIRMED'")):
    """Delete all discovery runs - REQUIRES confirmation"""
    env = os.environ.get("AOD_ENVIRONMENT", "development")

    # Block in production
    if env == "production":
        raise HTTPException(
            status_code=403,
            detail="DELETE ALL is disabled in production. Use run-specific deletion."
        )

    # Require explicit confirmation
    if confirm != "DELETE_ALL_CONFIRMED":
        raise HTTPException(
            status_code=400,
            detail="Must provide confirm='DELETE_ALL_CONFIRMED' to proceed"
        )

    db = await get_db_direct()
    deleted = await db.delete_all_runs()

    # Log for audit
    logger.warning("delete_all_runs.executed", extra={
        "deleted_count": deleted,
        "environment": env,
        "timestamp": datetime.utcnow().isoformat()
    })

    return {"message": f"Deleted {deleted} runs", "environment": env}
```

---

#### C2: CRITICAL - Add API Authentication

**Location:** `src/main.py`

**Current State:** Zero authentication. Anyone with network access can:
- Create runs (expensive compute)
- Read all data
- Delete all data
- Modify asset provisioning status

**Proposal:** Add API key middleware:
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    expected_key = os.environ.get("AOD_API_KEY")
    if not expected_key:
        # No key configured = allow (dev mode)
        return True
    if api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

# Apply to router
app.include_router(router, dependencies=[Depends(verify_api_key)])
```

**Environment Variables to Add:**
```
AOD_API_KEY=<secret-key-for-production>
AOD_ENVIRONMENT=production|staging|development
```

---

#### C3: HIGH - Add Environment-Aware Database Selection

**Location:** `db/database.py:22-39`

**Current State:** Single database URL, no environment awareness.

**Proposal:** Support environment-prefixed database URLs:
```python
def get_database_url() -> str:
    """Get database URL with environment awareness."""
    env = os.environ.get("AOD_ENVIRONMENT", "development")

    # Try environment-specific URL first
    env_specific_key = f"DATABASE_URL_{env.upper()}"
    db_url = os.environ.get(env_specific_key)

    # Fall back to generic
    if not db_url:
        db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError("No database configured.")

    # Log which database is being used
    logger.info("database.selected", extra={
        "environment": env,
        "source": env_specific_key if os.environ.get(env_specific_key) else "generic"
    })

    return db_url
```

**Recommended Environment Variables:**
```
# Production
DATABASE_URL_PRODUCTION=postgresql://prod-host/aod_prod

# Development
DATABASE_URL_DEVELOPMENT=postgresql://dev-host/aod_dev

# Staging
DATABASE_URL_STAGING=postgresql://staging-host/aod_staging
```

---

#### C4: HIGH - Add Run-Scoped Delete Instead of Global Delete

**Proposal:** Replace `delete_all_runs` with safer alternatives:

```python
@router.delete("/{run_id}")
async def delete_run(run_id: str, confirm: bool = Query(False)):
    """Delete a specific run and its associated data"""
    if not confirm:
        raise HTTPException(400, "Add ?confirm=true to delete")

    db = await get_db_direct()
    # Delete in order: findings, artifacts, assets, then run
    await db.delete_run_cascade(run_id)
    return {"message": f"Deleted run {run_id}"}

@router.delete("")
async def delete_all_runs(...):
    # Keep but add guards from C1
    ...
```

---

#### C5: MEDIUM - Restrict CORS in Production

**Location:** `src/main.py:18-24`

**Current:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DANGEROUS
    ...
)
```

**Proposal:**
```python
env = os.environ.get("AOD_ENVIRONMENT", "development")
allowed_origins = ["*"] if env == "development" else [
    "https://aod.yourcompany.com",
    "https://farm.yourcompany.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    ...
)
```

---

### Immediate Action Items (Priority Order)

| Priority | Item | Risk if Unaddressed |
|----------|------|---------------------|
| **P0** | Add `AOD_ENVIRONMENT` env var and check in `delete_all_runs` | Accidental prod data wipe |
| **P0** | Add `AOD_API_KEY` authentication | Unauthorized access/modification |
| **P1** | Add confirmation param to destructive endpoints | Accidental deletion |
| **P1** | Restrict CORS to known origins in production | CSRF attacks |
| **P2** | Add audit logging for all write operations | No forensics capability |
| **P2** | Add rate limiting | DoS risk |

---

## 1. Architecture & Design

### 1.1 Strong Points

- **Deterministic Pipeline**: 7-stage sequential pipeline ensures reproducibility
- **Pure Policy Engine**: `core/policy/engine.py` has no side effects - excellent testability
- **Evidence-Only Decisions**: No ML/anomaly scores, fully explainable outcomes
- **Clear Separation of Concerns**: Planes architecture isolates IdP/CMDB/Cloud/Finance logic

### 1.2 Proposals

#### P1.1: Extract Domain Matching Logic into Dedicated Module

**Location:** `pipeline/correlate_entities.py:627-1513` (886 lines in `correlate_to_plane`)

**Issue:** The `correlate_to_plane` function is 886 lines with deeply nested conditionals handling 15+ match methods.

**Proposal:**
```
pipeline/
├── correlate_entities.py          # Orchestration only (~200 lines)
├── matchers/
│   ├── base.py                    # PlaneMatch, MatchStatus, abstractions
│   ├── domain_matcher.py          # Domain/registered domain matching
│   ├── cmdb_authoritative.py      # CMDB canonical_domain, domains[], alias
│   ├── name_matcher.py            # canonical_name, fuzzy, contains
│   ├── vendor_matcher.py          # vendor, domain_vendor, vendor_fallback
│   └── token_matcher.py           # normalization_token, domain_token
```

**Benefit:** Each matcher becomes independently testable, ~100 lines each.

---

#### P1.2: Introduce Result Types for Error Handling

**Location:** Throughout pipeline modules

**Issue:** Functions return `None` or raise exceptions inconsistently. For example:
- `validate_snapshot()` raises `ValidationError`
- `apply_admission_criteria()` returns `AdmissionResult` with `.admitted=False`
- Database methods return `Optional[T]` or `None`

**Proposal:** Standardize on Result type pattern:
```python
from dataclasses import dataclass
from typing import TypeVar, Generic

T = TypeVar('T')

@dataclass
class Result(Generic[T]):
    value: Optional[T] = None
    error: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.error is None
```

**Benefit:** Explicit error handling, no silent None propagation.

---

#### P1.3: Decouple HTML Generation from Route Handlers

**Location:** `api/routes/catalog.py:125-558` (433 lines of inline HTML)

**Issue:** The `view_catalog` endpoint contains 433 lines of inline HTML/CSS/JS string construction.

**Proposal:**
- Move to Jinja2 templates in `templates/catalog/`
- Or extract to a dedicated `CatalogHTMLRenderer` class
- Consider replacing with a proper frontend build (client/ already exists)

**Benefit:** Separation of concerns, easier styling, cacheable assets.

---

## 2. Performance Optimizations

### 2.1 Proposals

#### P2.1: Add Database Connection Pool Health Monitoring

**Location:** `db/database.py:144-148`

**Issue:** Connection pool (`min_size=1, max_size=10`) has no health checks or metrics.

**Proposal:**
```python
async def get_pool_stats(self) -> dict:
    """Return pool health metrics for monitoring"""
    if self._pool:
        return {
            "size": self._pool.get_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
            "free_size": self._pool.get_idle_size(),
            "used_size": self._pool.get_size() - self._pool.get_idle_size(),
        }
    return {"status": "not_initialized"}
```

Add `/api/health/pool` endpoint for observability.

---

#### P2.2: Index Optimization for Large Snapshots

**Location:** `pipeline/build_plane_indexes.py`

**Issue:** Plane indexes are built in-memory with `dict[str, list[str]]`. For large tenants (10K+ records), linear scans in `by_name_words` can become slow.

**Proposal:**
- Consider using `collections.defaultdict(set)` instead of `defaultdict(list)` for deduplication
- Add bloom filter pre-check for common negative lookups
- Profile with production-scale snapshots

---

#### P2.3: Batch Database Writes with Chunking

**Location:** `db/database.py:949-1006`

**Issue:** `create_assets_batch` sends all assets in single `executemany`. For 1000+ assets, this can timeout.

**Proposal:**
```python
BATCH_CHUNK_SIZE = 500

async def create_assets_batch(self, assets: list[Asset]) -> None:
    if not assets:
        return
    for chunk in [assets[i:i+BATCH_CHUNK_SIZE] for i in range(0, len(assets), BATCH_CHUNK_SIZE)]:
        await self._insert_asset_chunk(chunk)
```

---

## 3. Code Quality

### 3.1 Proposals

#### P3.1: Type Annotations for All Public Functions

**Location:** Multiple files

**Issue:** Some functions lack complete type annotations:
- `_build_policy_asset_data()` returns `dict` (should be `dict[str, Any]` or typed dict)
- `disambiguate_matches()` returns complex tuple without type alias

**Proposal:** Create type aliases for complex return types:
```python
# In types.py
DisambiguationResult = tuple[AmbiguityCode, Optional[str], Optional[list[str]]]
PolicyAssetData = TypedDict('PolicyAssetData', {
    'domain': str,
    'in_idp': bool,
    'in_cmdb': bool,
    # ... etc
})
```

---

#### P3.2: Replace Magic Strings with Constants

**Location:** Throughout codebase

**Issue:** Magic strings like `"matched"`, `"ambiguous"`, `"unmatched"` appear in comparisons instead of using enums consistently.

**Examples:**
- `correlation.idp.status.value in ("matched", "ambiguous")` (line 423 catalog.py)
- Should be: `correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)`

**Proposal:** Audit and replace all string comparisons with enum usage.

---

#### P3.3: Reduce Code Duplication in Pipeline Executor

**Location:** `pipeline/pipeline_executor.py`

**Issue:** `run_pipeline_ephemeral()` and `execute_pipeline()` share ~80% of their logic but are separate 150+ line functions.

**Proposal:** Extract shared logic:
```python
def _run_pipeline_stages(
    data: dict,
    run_id: str,
    is_farm_source: bool,
    persist_results: bool = True,
    db: Optional[Database] = None
) -> PipelineResult:
    """Core pipeline logic - shared between ephemeral and persistent modes"""
    ...
```

---

#### P3.4: Consolidate Timestamp Handling

**Location:** Multiple modules

**Issue:** Inconsistent timezone handling:
- `output_contracts.py` uses `PST = timezone(timedelta(hours=-8))`
- `pipeline_executor.py` uses `timezone.utc`
- Some places parse ISO strings with `.replace('Z', '+00:00')`

**Proposal:** Create a centralized `utils/datetime_utils.py`:
```python
def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime string to UTC-aware datetime"""
    return datetime.fromisoformat(s.replace('Z', '+00:00'))
```

---

## 4. Security Considerations

### 4.1 Proposals

#### P4.1: Add Input Validation for API Query Parameters

**Location:** `api/routes/catalog.py:28`

**Issue:** `provisioning_status` query parameter is uppercased but not validated against enum values before filtering.

**Proposal:**
```python
@router.get("", response_model=CatalogResponse)
async def get_catalog(
    run_id: str,
    provisioning_status: Optional[ProvisioningStatus] = Query(
        None,
        description="Filter by provisioning status"
    )
):
```

Using the enum directly provides automatic validation.

---

#### P4.2: Sanitize HTML Output

**Location:** `api/routes/catalog.py:125-558`

**Issue:** Asset names and vendor names are interpolated directly into HTML without escaping.

```python
rows_html += f'<td style="...">{a.name or 'Unknown'}</td>'
```

If an asset name contains `<script>`, this creates XSS vulnerability.

**Proposal:**
```python
from html import escape

rows_html += f'<td style="...">{escape(a.name) or "Unknown"}</td>'
```

---

#### P4.3: Add Rate Limiting to Public Endpoints

**Location:** API routes

**Issue:** No rate limiting on API endpoints. A malicious actor could trigger expensive pipeline runs repeatedly.

**Proposal:** Add FastAPI rate limiting middleware:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/runs")
@limiter.limit("10/minute")
async def create_run(...):
```

---

## 5. Testing

### 5.1 Strong Points

- **18 test files** covering core functionality
- **98.7% reconciliation accuracy** validated in `test_golden_reconciliation.py`
- **Determinism tests** in `test_stability.py`
- **Edge case coverage** for TLD variants, zombie FPs, finance anchoring

### 5.2 Proposals

#### P5.1: Add Integration Tests for API Endpoints

**Issue:** No visible API integration tests. Route handlers are tested implicitly through pipeline tests.

**Proposal:** Add `tests/test_api_routes.py`:
```python
from fastapi.testclient import TestClient
from src.aod.main import app

client = TestClient(app)

def test_catalog_endpoint_returns_assets():
    # Create run, then query catalog
    response = client.get(f"/api/catalog?run_id={run_id}")
    assert response.status_code == 200
    assert "assets" in response.json()
```

---

#### P5.2: Add Property-Based Testing for Correlation Logic

**Issue:** Correlation matching has many edge cases. Current tests use specific examples.

**Proposal:** Add hypothesis-based property tests:
```python
from hypothesis import given, strategies as st

@given(domain=st.from_regex(r'[a-z0-9]+\.(com|io|org|net)', fullmatch=True))
def test_domain_normalization_is_idempotent(domain):
    result1 = normalize_domain(domain)
    result2 = normalize_domain(result1)
    assert result1 == result2
```

---

#### P5.3: Add Performance Regression Tests

**Issue:** No automated performance benchmarks. Pipeline slowdowns could go unnoticed.

**Proposal:** Add `tests/test_performance.py`:
```python
import time
import pytest

@pytest.mark.benchmark
def test_correlation_performance_under_1000_entities():
    # Generate 1000 test entities
    entities = generate_test_entities(1000)
    indexes = build_test_indexes(1000)

    start = time.perf_counter()
    results = correlate_entities_to_planes(entities, indexes)
    duration = time.perf_counter() - start

    assert duration < 2.0, f"Correlation took {duration}s, expected < 2s"
```

---

## 6. Maintainability

### 6.1 Proposals

#### P6.1: Add Architecture Decision Records (ADRs)

**Issue:** Design decisions are embedded in code comments but not formally documented.

**Proposal:** Create `docs/adr/` directory:
```
docs/adr/
├── 0001-deterministic-pipeline.md
├── 0002-evidence-only-decisions.md
├── 0003-iron-dome-validation.md
├── 0004-vendor-governance-propagation.md
└── template.md
```

---

#### P6.2: Consolidate Debug Scripts

**Location:** Root directory

**Issue:** 15+ debug/trace scripts at root level:
- `debug_vendor_governance.py`
- `debug_vendor_matching.py`
- `debug_teamsuite.py`
- `trace_idp_governance_aligned.py`
- etc.

**Proposal:** Move to `tools/debug/` and add a CLI entry point:
```
tools/debug/
├── __init__.py
├── cli.py              # Click CLI for all debug commands
├── vendor_governance.py
├── vendor_matching.py
└── idp_governance.py
```

Usage: `python -m tools.debug vendor-governance --asset-id=...`

---

#### P6.3: Add Structured Logging

**Location:** Throughout codebase

**Issue:** Logging uses both `logger.info("message", extra={...})` and f-string formatting inconsistently.

**Proposal:** Standardize on structured logging:
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "pipeline.stage_complete",
    stage="correlate",
    entity_count=len(entities),
    duration_ms=round(duration * 1000)
)
```

---

## 7. Documentation

### 7.1 Proposals

#### P7.1: Add OpenAPI Schema Documentation

**Issue:** API endpoints lack detailed OpenAPI documentation.

**Proposal:** Add response examples and detailed descriptions:
```python
@router.get(
    "",
    response_model=CatalogResponse,
    summary="Get assets for a run",
    description="""
    Retrieve all cataloged assets for a specific run.

    ## Filters
    - `provisioning_status`: Filter by ACTIVE, REVIEW, QUARANTINE, etc.

    ## Response
    Returns paginated list of Asset objects with full lens coverage.
    """,
    responses={
        404: {"description": "Run not found"},
        200: {"description": "Successful response with assets"}
    }
)
```

---

#### P7.2: Add Inline Documentation for Complex Algorithms

**Location:** `pipeline/correlate_entities.py`

**Issue:** Match method priority and disambiguation logic is complex but lacks flow diagrams.

**Proposal:** Add docstring with ASCII flow diagram:
```python
def correlate_to_plane(...):
    """
    Correlate entity to plane using multi-pass matching.

    Match Priority:
    ┌─────────────────────────────────────────────────────────┐
    │ AUTHORITATIVE (can assert governance)                   │
    │ ├─ 1. domain (exact eTLD+1 match)                      │
    │ ├─ 2. cmdb_canonical_domain                            │
    │ ├─ 3. cmdb_domains_array                               │
    │ ├─ 4. verified_alias_domain                            │
    │ └─ 5. canonical_name (exact)                           │
    ├─────────────────────────────────────────────────────────┤
    │ HEURISTIC (enrichment only)                            │
    │ ├─ 6. fuzzy (Levenshtein ≤ 2)                         │
    │ ├─ 7. contains (ratio ≥ 0.7)                          │
    │ ├─ 8. vendor                                           │
    │ └─ 9. normalization_token                              │
    └─────────────────────────────────────────────────────────┘
    """
```

---

## 8. Quick Wins (Low Effort, High Value)

| # | Proposal | Location | Effort | Impact |
|---|----------|----------|--------|--------|
| 1 | HTML escape asset names | catalog.py:306 | 5 min | Security |
| 2 | Use enum for status filter | catalog.py:28 | 10 min | Type safety |
| 3 | Add pool stats endpoint | database.py | 30 min | Observability |
| 4 | Consolidate timezone utils | new file | 1 hr | Consistency |
| 5 | Move debug scripts to tools/ | root dir | 30 min | Cleanliness |

---

## 9. Summary

**Ship Readiness:** READY (with caveats)
**Critical Issues:** 2 (Authentication, Destructive Endpoint Guards)
**Blocking Issues:** None (if deploying to isolated environment)

The codebase is production-ready with 98.7% accuracy. The pipeline and business logic are solid.

**However, shared dev/prod database requires immediate safeguards before production traffic.**

### Priority Recommendations

**CRITICAL (Before Prod Traffic):**
1. **C1** - Add environment guard to `DELETE /api/runs`
2. **C2** - Add API key authentication
3. **C5** - Restrict CORS to known origins

**HIGH (Soon After Launch):**
4. **C3** - Environment-aware database selection
5. **P4.2** - HTML escaping (XSS fix)

**MEDIUM (Future Iterations):**
6. **P1.1** - Matcher extraction for maintainability
7. **P5.1** - API integration tests
8. **P6.3** - Structured logging

---

### Quick Reference: Environment Variables to Add

```bash
# Required for production safety
AOD_ENVIRONMENT=production      # or development, staging
AOD_API_KEY=<your-secret-key>   # Required in production

# Optional: Separate databases per environment
DATABASE_URL_PRODUCTION=postgresql://prod-host/aod_prod
DATABASE_URL_DEVELOPMENT=postgresql://dev-host/aod_dev
```

---

*Review complete. No code changes were made. All proposals are documented for team discussion.*
