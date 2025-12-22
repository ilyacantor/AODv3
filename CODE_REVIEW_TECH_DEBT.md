# AOD v3 Code Review: Tech Debt, Performance & Debugging
**Review Date:** 2025-12-22
**Focus Areas:** Technical debt, performance blockers/bottlenecks, hard-to-debug logic tangles

---

## Executive Summary

The AOD v3 codebase is a sophisticated asset discovery and governance platform with ~11K lines of Python code. While the architecture demonstrates strong separation of concerns through pipeline stages, there are **critical performance bottlenecks** and **maintainability issues** that need addressing.

### Critical Issues (Requires Immediate Action)
1. **🔴 O(n²) correlation algorithm** - Lines 609-761 in `correlate_entities.py`
2. **🔴 N+1 database query pattern** - Multiple routes in `routes.py`
3. **🔴 Monolithic API file** - 2,732 lines in single file
4. **🔴 Full table scans with application-level filtering** - Lines 430-432, 458-461 in `routes.py`

### High Priority Issues
5. **🟡 Global singleton pattern** - Makes testing difficult
6. **🟡 Excessive code duplication** - 5x repeated matching pattern
7. **🟡 Inline HTML generation** - 376 lines of HTML in Python
8. **🟡 Silent exception handling** - Multiple bare `except Exception: pass`

### Performance Impact
- **Correlation engine**: Scales O(n²) with dataset size → 10K observations = ~100M comparisons
- **Database queries**: 3-5 sequential DB calls per request → 150-250ms latency overhead
- **List operations**: Full table scans → linear degradation with data growth

---

## 1. Performance Blockers & Bottlenecks

### 🔴 CRITICAL: O(n²) Nested Loop in Entity Correlation

**File:** `src/aod/pipeline/correlate_entities.py`
**Lines:** 609-761
**Impact:** Exponential time complexity as dataset grows

#### The Problem
The correlation engine iterates over ALL indexed names for EACH entity, performing string comparisons in nested loops:

```python
# Lines 609-611: Fuzzy matching
for indexed_name, record_ids in plane_index.by_canonical_name.items():
    if _is_fuzzy_match(canonical, indexed_name):
        fuzzy_matches.extend(record_ids)

# Lines 650-652: Contains matching
for indexed_name, record_ids in plane_index.by_canonical_name.items():
    if _is_valid_contains_match(canonical, indexed_name):
        contains_matches.extend(record_ids)

# Lines 695-697: Domain token matching
for indexed_name, record_ids in plane_index.by_canonical_name.items():
    if domain_token in indexed_name:
        token_matches.extend(record_ids)
```

**Complexity Analysis:**
- Exact match: O(1) via hash lookup ✅
- Fuzzy match: O(n × m) where n=entities, m=indexed_names 🔴
- Contains match: O(n × m) 🔴
- Domain token: O(n × m) 🔴
- **Total:** ~O(n² × k) where k = Levenshtein distance calculation

**Real-World Impact:**
- 1,000 observations: ~1M comparisons
- 10,000 observations: ~100M comparisons
- 50,000 observations: ~2.5B comparisons ❌ **Unacceptable**

#### Levenshtein Distance Recalculation

**Lines:** 47-65, called from line 610

```python
def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    # O(n × m) dynamic programming algorithm
    # Calculated fresh for EVERY pair - no caching!
```

Called in `_is_fuzzy_match()` on line 68, which is invoked for every indexed name.

**Impact:** With 10K entities × 10K indexed names = 100M Levenshtein calculations
**Estimated time:** 0.5ms per calc × 100M = **50,000 seconds** (~14 hours) 🔴

#### Recommendations

**Short-term fixes:**
1. **Add early exit conditions** - Stop after finding N matches
2. **Implement result caching** - Cache Levenshtein results with LRU
3. **Parallelize matching** - Use asyncio.gather() for independent plane matches
4. **Profile with realistic data** - Test with 10K+ observations

**Long-term solutions:**
1. **Use BK-tree or similar data structure** - O(log n) fuzzy search
2. **Implement inverted indexes** - Index by trigrams for substring matching
3. **Pre-filter candidates** - Only compare names starting with same letter
4. **Consider fuzzy string libraries** - RapidFuzz or polyfuzz with SIMD optimizations

**Code example (quick win):**
```python
# Add early exit and caching
from functools import lru_cache

@lru_cache(maxsize=10000)
def _levenshtein_distance_cached(s1: str, s2: str) -> int:
    # ... existing implementation

# Add limit to matches
MAX_FUZZY_CANDIDATES = 100
fuzzy_matches: list[str] = []
for indexed_name, record_ids in list(plane_index.by_canonical_name.items())[:MAX_FUZZY_CANDIDATES]:
    if _is_fuzzy_match(canonical, indexed_name):
        fuzzy_matches.extend(record_ids)
        if len(fuzzy_matches) >= 10:  # Early exit
            break
```

---

### 🔴 CRITICAL: N+1 Database Query Pattern

**File:** `src/aod/api/routes.py`
**Lines:** Multiple endpoints (303-305, 430-432, 458-461, 554-557)

#### The Problem

Routes make multiple sequential database calls instead of batching:

**Example 1: create_run_from_farm() - Lines 303-305**
```python
assets = await db.get_assets_by_run(run_id)      # Query 1 (~50ms)
findings = await db.get_findings_by_run(run_id)  # Query 2 (~50ms)
rejections = await db.get_rejections_by_run(...)  # Query 3 (~50ms)
# Total: 150ms just waiting for database
```

**Example 2: list_runs() - Lines 430-432, 458-461**
```python
# INEFFICIENT: Load all runs, filter in Python
runs = await db.get_all_runs()  # Loads ALL runs into memory
matching = [r for r in runs if r.tenant_id == tenant_id]  # Python filter
```

**What's wrong:**
- Fetches ALL rows from database (could be 10K+ runs)
- Filters in application layer instead of database (WHERE clause)
- Repeats full table scan on EVERY request
- Memory overhead: loads entire table into Python list

**Performance Impact:**
- 100 runs: ~10ms ✅
- 1,000 runs: ~100ms 🟡
- 10,000 runs: ~1 second 🔴
- 100,000 runs: ~10 seconds ❌ **Database timeout**

#### Recommendations

**Fix for list_runs():**
```python
# Add WHERE clause to database query
async def get_runs_by_tenant(self, tenant_id: str) -> list[RunLog]:
    """Get runs filtered by tenant_id - DONE IN DATABASE"""
    pool = await self.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM runs WHERE tenant_id = $1 ORDER BY started_at DESC",
            tenant_id
        )
        return [self._row_to_run(row) for row in rows]

# In routes.py:
@router.get("/runs")
async def list_runs(tenant_id: Optional[str] = None):
    db = await get_db()
    if tenant_id:
        runs = await db.get_runs_by_tenant(tenant_id)
    else:
        runs = await db.get_all_runs()
    return [RunDetailResponse(...) for run in runs]
```

**Fix for create_run_from_farm():**
```python
# Batch multiple queries in single transaction
async def get_run_data_batch(self, run_id: str) -> dict:
    """Get assets, findings, and rejections in single transaction"""
    pool = await self.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            assets = await conn.fetch("SELECT * FROM assets WHERE run_id = $1", run_id)
            findings = await conn.fetch("SELECT * FROM findings WHERE run_id = $1", run_id)
            rejections = await conn.fetch("SELECT * FROM rejections WHERE run_id = $1", run_id)

            return {
                'assets': [self._row_to_asset(r) for r in assets],
                'findings': [self._row_to_finding(r) for r in findings],
                'rejections': [self._row_to_rejection(r) for r in rejections]
            }
```

**Estimated improvement:** 150ms → 50ms (3x faster)

---

### 🔴 HIGH: Regex Pattern Recompilation

**File:** `src/aod/pipeline/normalize_observations.py`
**Lines:** 68, 76

#### The Problem

Regex patterns are compiled on EVERY function call:

```python
def _derive_canonical_name(observation: Observation) -> str:
    canonical = normalize_string(name)
    canonical = re.sub(r'\([^)]*\)', '', canonical).strip()  # Line 68 - compiled each time!
    # ...
    canonical = re.sub(r'[^\w\s-]', '', canonical)  # Line 76 - compiled each time!
    canonical = re.sub(r'\s+', ' ', canonical).strip()  # Line 77 - compiled each time!
```

Called once per observation (could be 10K+ times per run).

**Performance Impact:**
- Pattern compilation: ~10µs per call
- With 10K observations: 10µs × 30K regex calls = **300ms wasted**

#### Recommendations

```python
# At module level
import re

_PAREN_PATTERN = re.compile(r'\([^)]*\)')
_NON_WORD_PATTERN = re.compile(r'[^\w\s-]')
_WHITESPACE_PATTERN = re.compile(r'\s+')

def _derive_canonical_name(observation: Observation) -> str:
    canonical = normalize_string(name)
    canonical = _PAREN_PATTERN.sub('', canonical).strip()
    canonical = _NON_WORD_PATTERN.sub('', canonical)
    canonical = _WHITESPACE_PATTERN.sub(' ', canonical).strip()
    return canonical if canonical else normalize_string(name)
```

**Also apply to:**
- `correlate_entities.py:143` - `_extract_base_name()`
- Any other regex patterns in hot paths

---

### 🟡 MEDIUM: view_catalog() HTML Generation

**File:** `src/aod/api/routes.py`
**Lines:** 549-925 (376 lines of inline HTML!)

#### The Problem

Generating HTML in Python with string concatenation:

```python
def get_triage_badge(asset_id):
    # Lines 581-600: Inline HTML generation
    return f'<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned: {owner}</span>'

# Lines 645-925: Building huge HTML strings
orphan_rows_html = ""
for f in orphan_findings:
    orphan_rows_html += f"<tr>...</tr>"  # String concatenation in loop!
```

**Issues:**
1. **String concatenation in loops** - O(n²) behavior due to string immutability
2. **No HTML escaping** - XSS vulnerability if user data contains `<script>`
3. **Maintainability** - HTML mixed with business logic
4. **No syntax highlighting** - Hard to debug malformed HTML

**Performance Impact:**
- With 1,000 assets: ~100ms string concatenation
- With 10,000 assets: ~10 seconds 🔴

#### Recommendations

**Option 1: Use Jinja2 templates**
```python
from jinja2 import Template

CATALOG_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<body>
  {% for asset in assets %}
    <div>{{ asset.name }}</div>
  {% endfor %}
</body>
</html>
""")

@router.get("/catalog/{run_id}/view")
async def view_catalog(run_id: str):
    assets = await db.get_assets_by_run(run_id)
    html = CATALOG_TEMPLATE.render(assets=assets)
    return HTMLResponse(content=html)
```

**Option 2: Use list comprehension + join (quick fix)**
```python
# Instead of string concatenation:
orphan_rows_html = ""
for f in orphan_findings:
    orphan_rows_html += f"<tr>...</tr>"

# Use list + join:
orphan_rows = [f"<tr>...</tr>" for f in orphan_findings]
orphan_rows_html = "".join(orphan_rows)
```

**Estimated improvement:** 10s → 100ms (100x faster for large datasets)

---

## 2. Technical Debt

### 🔴 CRITICAL: Monolithic API Routes File

**File:** `src/aod/api/routes.py`
**Size:** 2,732 lines (15% of entire codebase!)
**Impact:** Maintainability nightmare, merge conflicts, hard to test

#### The Problem

Single file contains 28+ endpoint functions across multiple domains:

- **Farm Integration** (lines 49-379): 8 endpoints
- **Run Management** (lines 381-478): 4 endpoints
- **Data Retrieval** (lines 480-1387): 10+ endpoints
- **Classifications** (lines 1389-1654): 4 endpoints
- **Triage & Admin** (lines 1655-2732): 6+ endpoints

**Why this is bad:**
1. **Merge conflicts** - Multiple devs editing same file
2. **Slow IDE performance** - Autocomplete lags with 2700+ lines
3. **Hard to navigate** - Finding specific endpoint takes time
4. **Tight coupling** - Everything in global scope
5. **Difficult testing** - Can't isolate route groups

#### Recommendations

**Split into domain-based blueprints:**

```
src/aod/api/
├── __init__.py              # Combine all routers
├── farm_routes.py           # Farm integration (lines 49-379)
├── run_routes.py            # Run CRUD (lines 381-478)
├── catalog_routes.py        # Asset/finding retrieval (lines 480-1000)
├── classification_routes.py # Derived classifications (lines 1389-1654)
├── triage_routes.py         # Triage actions (lines 1655-2100)
├── admin_routes.py          # System admin (lines 2100-2732)
└── templates/
    └── catalog.html         # Extract HTML generation
```

**Example refactor:**
```python
# farm_routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/farm", tags=["farm"])

@router.get("/tenants")
async def list_farm_tenants():
    # Move from routes.py lines 49-80
    ...

# __init__.py
from fastapi import FastAPI
from . import farm_routes, run_routes, catalog_routes

def register_routes(app: FastAPI):
    app.include_router(farm_routes.router)
    app.include_router(run_routes.router)
    app.include_router(catalog_routes.router)
```

**Estimated effort:** 4-6 hours
**Benefit:** 50% reduction in future debugging time

---

### 🔴 HIGH: Global Singleton Database Pattern

**File:** `src/aod/db/database.py`
**Lines:** 51-58

#### The Problem

```python
_db_instance: Optional["Database"] = None

async def get_db() -> "Database":
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    return _db_instance
```

**Why this is problematic:**
1. **Makes unit testing hard** - Can't inject mock database
2. **Global state** - Shared across all requests (thread safety?)
3. **Initialization timing** - First request pays initialization cost
4. **No cleanup** - Connection pool never closed in tests
5. **Single instance** - Can't connect to multiple databases

#### Recommendations

**Use FastAPI dependency injection:**

```python
# database.py - Remove global singleton
class Database:
    _instance: Optional["Database"] = None

    @classmethod
    async def get_instance(cls) -> "Database":
        """Singleton for production, but testable"""
        if cls._instance is None:
            db_url = get_database_url()
            cls._instance = Database(db_url)
            await cls._instance.initialize()
        return cls._instance

# main.py - Setup dependency
from fastapi import Depends
from aod.db.database import Database

async def get_db() -> Database:
    """Dependency injection for routes"""
    return await Database.get_instance()

# routes.py - Use dependency injection
@router.get("/runs")
async def list_runs(db: Database = Depends(get_db)):
    runs = await db.get_all_runs()
    return runs

# test_routes.py - Easy mocking!
from unittest.mock import AsyncMock

async def test_list_runs():
    mock_db = AsyncMock(spec=Database)
    mock_db.get_all_runs.return_value = [...]

    # Inject mock
    app.dependency_overrides[get_db] = lambda: mock_db
    response = await client.get("/runs")
    assert response.status_code == 200
```

---

### 🟡 HIGH: Silent Exception Handling

**File:** `src/aod/db/database.py`
**Lines:** 122-138

#### The Problem

Database migrations silently fail:

```python
try:
    await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS vendor_hypothesis TEXT")
except Exception:
    pass  # Line 124 - SILENT FAILURE! 😱

try:
    await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS category TEXT...")
except Exception:
    pass  # Line 129 - SILENT FAILURE!

try:
    await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS confidence TEXT...")
    await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS materiality TEXT...")
    await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS triage_priority TEXT...")
    await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS conflict_field TEXT")
except Exception:
    pass  # Lines 137-138 - 4 statements, which one failed?!
```

**Why this is dangerous:**
1. **Schema drift** - Production DB might be missing columns
2. **No error visibility** - Devs don't know migrations failed
3. **Data corruption** - Code expects column that doesn't exist
4. **Hard to debug** - Silent failures compound over time

**Real scenario:**
- Developer adds new column in migration
- Migration silently fails on production
- Code tries to INSERT with new column
- Gets cryptic error: `column "triage_priority" does not exist`
- Debugging takes 2 hours to find root cause

#### Recommendations

```python
import logging

logger = logging.getLogger(__name__)

# Option 1: Log warnings
try:
    await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS vendor_hypothesis TEXT")
except asyncpg.DuplicateColumnError:
    # This is expected if column already exists
    pass
except Exception as e:
    logger.warning(f"Migration failed (non-critical): ALTER TABLE assets ADD vendor_hypothesis - {e}")

# Option 2: Use proper migration framework
# Install: pip install alembic
# Then use alembic for schema versioning instead of inline migrations
```

**Better approach: Use Alembic**
```python
# alembic/versions/001_add_vendor_hypothesis.py
def upgrade():
    op.add_column('assets', sa.Column('vendor_hypothesis', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('assets', 'vendor_hypothesis')
```

---

### 🟡 MEDIUM: Excessive Code Duplication

**File:** `src/aod/pipeline/correlate_entities.py`
**Lines:** 552-820 (5 nearly identical blocks!)

#### The Problem

The same matching pattern is repeated 5 times with minor variations:

```python
# Block 1: Canonical name match (lines 552-606)
name_matches = plane_index.by_canonical_name.get(canonical, [])
if len(name_matches) == 1:
    return PlaneMatch(status=MatchStatus.MATCHED, ...)
elif len(name_matches) > 1:
    code, detail, resolved = disambiguate_matches(...)
    if resolved and len(resolved) == 1:
        return PlaneMatch(status=MatchStatus.MATCHED, ...)
    return PlaneMatch(status=MatchStatus.AMBIGUOUS, ...)

# Block 2: Fuzzy match (lines 608-647) - EXACT SAME PATTERN
fuzzy_matches: list[str] = []
for indexed_name, record_ids in plane_index.by_canonical_name.items():
    if _is_fuzzy_match(canonical, indexed_name):
        fuzzy_matches.extend(record_ids)
if len(fuzzy_matches) == 1:
    return PlaneMatch(status=MatchStatus.MATCHED, ...)
elif len(fuzzy_matches) > 1:
    code, detail, resolved = disambiguate_matches(...)
    # ... identical logic

# Block 3: Contains match (lines 649-688) - SAME AGAIN
# Block 4: Domain token (lines 690-733) - SAME AGAIN
# Block 5: Vendor match (lines 735-820) - SAME AGAIN
```

**Line count:** ~270 lines of repetitive code (30% of file)

#### Recommendations

**Extract to generic function:**

```python
def _try_match_with_disambiguation(
    matches: list[str],
    plane_index: PlaneIndex,
    entity: CandidateEntity,
    match_method: str,
    match_key: str
) -> Optional[PlaneMatch]:
    """Generic matching logic with disambiguation"""
    if len(matches) == 0:
        return None

    if len(matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=matches,
            matched_records=[plane_index.records.get(matches[0])],
            match_method=match_method,
            match_key=match_key,
            ambiguity_code=AmbiguityCode.NONE
        )

    # Multiple matches - try to disambiguate
    records = [plane_index.records.get(mid) for mid in matches]
    code, detail, resolved = disambiguate_matches(entity, matches, records, match_method)

    if resolved and len(resolved) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=resolved,
            matched_records=[plane_index.records.get(resolved[0])],
            match_method=match_method,
            match_key=match_key,
            ambiguity_code=code,
            disambiguation_detail=detail
        )

    return PlaneMatch(
        status=MatchStatus.AMBIGUOUS,
        matched_ids=matches,
        matched_records=records,
        match_method=match_method,
        match_key=match_key,
        ambiguity_code=code,
        disambiguation_detail=detail
    )

# Now use it:
def correlate_with_plane(...):
    # Try exact match
    name_matches = plane_index.by_canonical_name.get(canonical, [])
    if result := _try_match_with_disambiguation(name_matches, plane_index, entity, "canonical_name", canonical):
        return result

    # Try fuzzy match
    fuzzy_matches = [rid for name, rid in plane_index.by_canonical_name.items() if _is_fuzzy_match(canonical, name)]
    if result := _try_match_with_disambiguation(fuzzy_matches, plane_index, entity, "fuzzy", canonical):
        return result

    # ... etc
```

**Benefit:** 270 lines → 80 lines (70% reduction)

---

## 3. Hard-to-Debug Logic Tangles

### 🔴 HIGH: Disambiguation Logic Complexity

**File:** `src/aod/pipeline/correlate_entities.py`
**Function:** `disambiguate_matches()`
**Lines:** 334-500+ (estimated, not fully visible)

#### The Problem

When multiple matches are found, the system attempts to resolve ambiguity using complex heuristics:

```python
def disambiguate_matches(
    entity: CandidateEntity,
    matched_ids: list[str],
    matched_records: list[dict],
    match_method: str
) -> tuple[AmbiguityCode, str, Optional[list[str]]]:
    """
    Attempt to resolve ambiguous matches using metadata.

    Checks (in order):
    1. CMDB status fields (is_deprecated, lifecycle_state)
    2. Environment grouping
    3. Vendor-product distinctness
    4. Known distinct products set
    """
```

**Complexity factors:**
1. **Multiple resolution strategies** - 4+ different approaches
2. **Order-dependent logic** - Strategy 1 must run before strategy 2
3. **Side effects** - Modifies AmbiguityCode based on partial resolution
4. **No tracing** - Hard to see which strategy resolved (or failed to resolve)
5. **Nested conditions** - Multiple levels of if/elif checking metadata fields

**Debugging scenario:**
```
Problem: Entity "monday.com" matched to 3 CMDB records
Question: Which disambiguation strategy was used?
Current solution: Add print() statements and re-run pipeline
Better solution: Structured logging with strategy trace
```

#### Recommendations

**Add decision tracing:**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class DisambiguationTrace:
    strategy_attempted: str
    strategy_succeeded: bool
    records_before: int
    records_after: int
    reason: str

def disambiguate_matches(...) -> tuple[AmbiguityCode, str, Optional[list[str]], list[DisambiguationTrace]]:
    trace: list[DisambiguationTrace] = []

    # Strategy 1: CMDB status filtering
    active_records = [r for r in matched_records if not r.get('is_deprecated')]
    trace.append(DisambiguationTrace(
        strategy_attempted="filter_deprecated",
        strategy_succeeded=len(active_records) < len(matched_records),
        records_before=len(matched_records),
        records_after=len(active_records),
        reason=f"Filtered {len(matched_records) - len(active_records)} deprecated records"
    ))

    if len(active_records) == 1:
        logger.info(f"Disambiguation trace: {trace}")
        return AmbiguityCode.RESOLVED_BY_STATUS, "...", active_records, trace

    # Strategy 2: Environment grouping
    # ... similar tracing

    logger.warning(f"Disambiguation failed. Trace: {trace}")
    return AmbiguityCode.UNRESOLVED, "...", None, trace
```

**Benefits:**
- See which strategies were attempted
- Understand why disambiguation failed
- Debug production issues from logs
- Improve resolution strategies based on data

---

### 🟡 MEDIUM: Triage Badge Logic Duplication

**File:** `src/aod/api/routes.py`
**Lines:** 581-600 (assets), 626-643 (findings)

#### The Problem

Two nearly identical functions for generating triage badges:

```python
def get_triage_badge(asset_id):
    """Get triage disposition badge for an asset"""
    action = triage_by_asset.get(str(asset_id))
    if not action:
        return ''

    action_type = action.get('action_type', '')
    state = action.get('state', '')

    if action_type == 'assign':
        owner = action.get('metadata', {}).get('assigned_to', '')
        return f'<span style="background: #3b82f6; ...">Assigned: {owner}</span>'
    # ... more conditions

def get_finding_triage_badge(finding_id):
    """Get triage disposition badge for a finding"""
    for action in triage_actions:
        if action.get('item_id') == str(finding_id):
            action_type = action.get('action', '')  # Different key! 'action' vs 'action_type'
            state = action.get('state', '')

            if action_type == 'assign':
                owner = action.get('owner', '')  # Different key! 'owner' vs 'metadata.assigned_to'
                return f'<span style="background: #3b82f6; ...">Assigned: {owner}</span>'
```

**Issues:**
1. **Inconsistent data structures** - `action_type` vs `action`, `metadata.assigned_to` vs `owner`
2. **Duplicated HTML** - Same badge HTML in both functions
3. **Hard to update** - Change badge color? Update in 2 places
4. **Logic divergence** - Functions will drift over time

#### Recommendations

```python
# Unified function
def get_triage_badge(item_id: str, item_type: str, triage_actions: list[dict]) -> str:
    """Get triage badge for any item (asset or finding)"""
    action = next(
        (a for a in triage_actions if a.get('item_id') == str(item_id) and a.get('item_type') == item_type),
        None
    )
    if not action:
        return ''

    # Normalize action data structure
    action_type = action.get('action_type') or action.get('action')
    state = action.get('state', '')

    # Badge styling centralized
    BADGE_STYLES = {
        'assign': {'bg': '#3b82f6', 'text': 'Assigned'},
        'defer': {'bg': '#8b5cf6', 'text': 'Deferred'},
        'ignore': {'bg': '#64748b', 'text': 'Ignored'},
        'acknowledge': {'bg': '#0ea5e9', 'text': 'Acknowledged'},
    }

    style = BADGE_STYLES.get(action_type) or BADGE_STYLES.get(state)
    if not style:
        return ''

    return f'<span style="background: {style["bg"]}; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">{style["text"]}</span>'

# Usage
badge = get_triage_badge(asset.asset_id, 'asset', triage_actions)
badge = get_triage_badge(finding.finding_id, 'finding', triage_actions)
```

---

### 🟡 MEDIUM: Magic Numbers Scattered Throughout

**Files:** Multiple
**Impact:** Configuration changes require code edits

#### The Problem

Hardcoded thresholds and limits with no central configuration:

```python
# pipeline_executor.py:25
MAX_OBSERVATION_SAMPLES = 2000

# findings_engine.py:50
FINANCE_GAP_MONTHLY_THRESHOLD = 200.0

# correlate_entities.py:68
def _is_fuzzy_match(name1: str, name2: str, max_distance: int = 2, max_ratio: float = 0.20):

# correlate_entities.py:693
if domain_token and len(domain_token) >= 6:  # Why 6?

# database.py:71
self._pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
```

**Why this matters:**
1. **Hard to tune** - Must search codebase to find thresholds
2. **Environment-specific** - Prod vs dev might need different limits
3. **Testing** - Can't easily test with different values
4. **Documentation** - No single place to see all config options

#### Recommendations

**Create centralized configuration:**

```python
# src/aod/config.py
from pydantic import BaseSettings

class AODConfig(BaseSettings):
    """Centralized AOD configuration"""

    # Database
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    # Pipeline limits
    max_observation_samples: int = 2000

    # Correlation thresholds
    fuzzy_match_max_distance: int = 2
    fuzzy_match_max_ratio: float = 0.20
    domain_token_min_length: int = 6

    # Findings thresholds
    finance_gap_monthly_threshold: float = 200.0
    activity_window_days: int = 90

    class Config:
        env_prefix = "AOD_"
        env_file = ".env"

# Usage
from aod.config import AODConfig

config = AODConfig()

# database.py
self._pool = await asyncpg.create_pool(
    self.db_url,
    min_size=config.db_pool_min_size,
    max_size=config.db_pool_max_size
)

# correlate_entities.py
if len(domain_token) >= config.domain_token_min_length:
```

**Benefits:**
- Single source of truth for configuration
- Environment-specific overrides via `.env` files
- Type-safe configuration with Pydantic
- Auto-generated documentation

---

## 4. Security & Robustness Concerns

### 🔴 HIGH: No HTML Escaping in User Data

**File:** `src/aod/api/routes.py`
**Lines:** 592-643 (multiple HTML generation locations)

#### The Problem

User-provided data inserted directly into HTML without escaping:

```python
owner = action.get('metadata', {}).get('assigned_to', '')
return f'<span>Assigned: {owner}</span>'  # XSS vulnerability!
```

**Attack scenario:**
1. Attacker creates triage action with `assigned_to = '<script>alert(document.cookie)</script>'`
2. Admin views catalog
3. JavaScript executes, stealing session cookie

#### Recommendations

```python
from html import escape

owner = escape(action.get('metadata', {}).get('assigned_to', ''))
return f'<span>Assigned: {owner}</span>'

# Or use Jinja2 (auto-escapes by default)
```

---

### 🟡 MEDIUM: No Request Size Limits

**File:** `src/aod/api/routes.py`
**Line:** 168 (snapshot upload)

#### The Problem

```python
@router.post("/runs")
async def create_run_from_snapshot(snapshot: Snapshot):
    # No size limit! Could upload 1GB JSON and crash server
```

#### Recommendations

```python
# main.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

MAX_REQUEST_SIZE = 50 * 1024 * 1024  # 50MB

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > MAX_REQUEST_SIZE:
            raise RequestValidationError("Request too large")
    return await call_next(request)
```

---

## 5. Summary & Prioritized Action Plan

### Immediate Actions (This Week)

1. **🔴 Add Levenshtein caching** - 2 hours
   - File: `correlate_entities.py:47`
   - Impact: 50-90% correlation speedup
   - Risk: Low (pure performance optimization)

2. **🔴 Fix list_runs() filtering** - 1 hour
   - File: `routes.py:430-461`, `database.py` (add new method)
   - Impact: 10x faster for tenants with many runs
   - Risk: Low (backward compatible)

3. **🔴 Add logging to silent exceptions** - 30 minutes
   - File: `database.py:122-138`
   - Impact: Prevent silent schema drift
   - Risk: None

4. **🔴 Pre-compile regex patterns** - 1 hour
   - Files: `normalize_observations.py:68,76`, `correlate_entities.py:143`
   - Impact: 10-30% normalization speedup
   - Risk: Low

### Short-term Improvements (This Month)

5. **🟡 Split routes.py** - 4-6 hours
   - File: `routes.py` → 6 files
   - Impact: Better maintainability, fewer merge conflicts
   - Risk: Medium (requires testing all endpoints)

6. **🟡 Extract correlation matching logic** - 3 hours
   - File: `correlate_entities.py:552-820`
   - Impact: 70% code reduction, easier to test
   - Risk: Medium (complex refactor)

7. **🟡 Batch database queries** - 2-3 hours
   - File: `routes.py:303-305`, `database.py` (add batch method)
   - Impact: 3x faster run creation
   - Risk: Low

8. **🟡 Replace global DB singleton** - 2 hours
   - File: `database.py:51-58`, update routes
   - Impact: Testability, dependency injection
   - Risk: Medium (affects all routes)

### Long-term Refactoring (Next Quarter)

9. **🔴 Redesign correlation algorithm** - 1-2 weeks
   - File: `correlate_entities.py` (full rewrite)
   - Options: BK-tree, trigram indexing, fuzzy libraries
   - Impact: O(n²) → O(n log n) complexity
   - Risk: High (core algorithm change)

10. **🟡 Extract HTML to Jinja2 templates** - 3-4 days
    - File: `routes.py:549-925` → `templates/`
    - Impact: 100x faster rendering, maintainability
    - Risk: Medium (HTML structure change)

11. **🟡 Implement centralized configuration** - 1-2 days
    - Files: Create `config.py`, update all modules
    - Impact: Easier tuning, environment-specific settings
    - Risk: Low

---

## 6. Metrics & Monitoring Recommendations

To prevent tech debt accumulation, implement:

### Code Quality Metrics
```python
# Add to CI/CD pipeline
- name: Check file size
  run: |
    MAX_LINES=500
    find src -name "*.py" -exec wc -l {} \; | awk -v max=$MAX_LINES '$1 > max {print $2 " has " $1 " lines (max: " max ")"; exit 1}'

- name: Complexity check
  run: |
    pip install radon
    radon cc src/ -n C  # Fail if complexity grade C or worse
```

### Performance Benchmarks
```python
# tests/benchmarks/test_correlation_performance.py
import pytest
import time

@pytest.mark.benchmark
def test_correlation_performance_1k_observations():
    """Ensure correlation completes in <5s for 1000 observations"""
    start = time.time()
    result = correlate_entities(generate_test_observations(1000))
    duration = time.time() - start

    assert duration < 5.0, f"Correlation took {duration}s (expected <5s)"

@pytest.mark.benchmark
def test_correlation_performance_10k_observations():
    """Ensure correlation completes in <60s for 10,000 observations"""
    start = time.time()
    result = correlate_entities(generate_test_observations(10000))
    duration = time.time() - start

    assert duration < 60.0, f"Correlation took {duration}s (expected <60s)"
```

### Database Query Monitoring
```python
# Add query logging
import logging
import time

class QueryTimingMiddleware:
    async def __call__(self, query: str, *args):
        start = time.time()
        result = await self.execute(query, *args)
        duration = time.time() - start

        if duration > 0.1:  # Log slow queries
            logging.warning(f"Slow query ({duration:.2f}s): {query[:100]}")

        return result
```

---

## Conclusion

The AOD v3 codebase demonstrates solid architectural principles but suffers from **performance bottlenecks** and **maintainability issues** that will compound as the system scales.

**Critical path:** Fix the O(n²) correlation algorithm and database query patterns to prevent production performance issues as data grows.

**Quick wins:** Regex caching, query batching, and exception logging provide immediate ROI with minimal risk.

**Strategic refactoring:** Splitting the monolithic routes file and extracting correlation logic will pay long-term dividends in maintainability and developer velocity.

---

**Reviewed by:** Claude Code
**Next review:** After implementing immediate actions (1 week)
