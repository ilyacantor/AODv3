# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence and generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets. This provides a clear, auditable view of an organization's digital footprint, supporting robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## Tech Stack
- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **PostgreSQL** persistence via **asyncpg**
- **Uvicorn** server
- **httpx** for async HTTP to Farm

## Project Architecture

```
src/
├── main.py                 # FastAPI application entry point
└── aod/
    ├── api/
    │   └── routes/         # Modular API endpoints
    ├── db/
    │   └── database.py     # PostgreSQL persistence layer (asyncpg)
    ├── models/
    │   ├── input_contracts.py   # Pydantic models for snapshot input
    │   └── output_contracts.py  # Pydantic models for assets, findings
    ├── farm_reconcile.py   # Farm auto-sync and reconciliation
    └── pipeline/
        ├── validate_snapshot.py      # Stage 1: Schema validation
        ├── normalize_observations.py # Stage 2: Normalize names/domains
        ├── build_plane_indexes.py    # Stage 3: Build plane indexes
        ├── correlate_entities.py     # Stage 4: Three-pass correlation
        ├── admission.py              # Stage 5: Admission criteria
        ├── artifact_handler.py       # Stage 6: Artifact handling
        ├── findings_engine.py        # Stage 7: Generate findings
        ├── pipeline_executor.py      # Orchestrate all stages
        ├── derived_classifications.py # Shadow/Zombie computation
        └── aod_agent_reconcile.py    # Emit actual results for Farm

templates/
└── index.html              # AOD Console UI

static/
├── css/main.css            # Styles
└── js/app.js               # Frontend logic

tests/
└── test_*.py               # Test suites
```

## Core Design Principles (Non-Negotiables)

1. **No ground truth ingestion** - Rejects banned fields like `is_shadow_it`, `ground_truth`, `inCMDB`. If present, marks run as `INVALID_INPUT_CONTRACT`
2. **No ML/anomaly scores** - Only deterministic rules and explainable correlation
3. **Deterministic** - Same snapshot + same config produces identical outputs with stable ordering
4. **Evidence-only decisions** - Admission and findings derived only from plane evidence, never upstream labels
5. **Assets vs Artifacts** - Dashboards/reports/calculators are artifacts, never assets; they don't inflate asset counts

## Pipeline Architecture
The system employs a 7-stage sequential pipeline: validation, normalization, indexing, correlation, admission, artifact handling, and findings generation.

## Database Configuration
Single DB selection rule (no fallbacks):
- Priority: `SUPABASE_DB_URL` > `DATABASE_URL`
- If neither is set, application fails fast with clear error
- No SQLite fallback or other defaults allowed
- `IGNORE_REPLIT_DB=true` ignores any REPLIT* env vars

## API Endpoints

### Core Discovery
- `POST /api/runs/from-farm` - Create discovery run from Farm snapshot
- `GET /api/runs` - List all runs
- `GET /api/runs/{run_id}` - Get run details
- `GET /api/v1/catalog?run_id=X` - Get assets for a run
- `GET /api/v1/findings?run_id=X` - Get findings for a run

### Catalog & Triage
- `GET /api/v1/catalog?provisioning_status=active` - Filtered view
- `GET /api/v1/catalog/dcl?run_id=X` - DCL export (ACTIVE only)
- `GET /api/handoff/aam-manifest?run_id=X` - AAM Target Manifest
- `POST /api/triage/action` - Submit triage action
- `DELETE /api/triage/action/{run_id}/{item_id}` - Undo triage action

### Farm Integration
- `GET /api/farm/snapshots?tenant_id=...` - List available snapshots from Farm
- `GET /api/runs/{run_id}/reconcile-payload` - Get reconciliation payload
- `POST /api/runs/resync` - Re-trigger Farm callback

### Debug & Health
- `GET /api/health` - Health check
- `POST /api/debug/zombie-explain` - Zombie classification explanations
- `POST /api/debug/aod-agent-reconcile` - AOD Agent diagnostic reconciliation

## Run Status Values
- `UPSTREAM_ERROR` - Farm unreachable or HTTP error
- `INVALID_SNAPSHOT` - Schema mismatch or wrong version
- `INVALID_INPUT_CONTRACT` - Banned fields present
- `COMPLETED_NO_ASSETS` - Pipeline completed, nothing admitted
- `COMPLETED_WITH_RESULTS` - Normal success with assets/findings

## Derived Classifications

### Activity Status (Dec 2025)
- **RECENT** = has activity timestamp within 90-day window
- **STALE** = has activity timestamp outside 90-day window
- **NONE** = no activity timestamps (indeterminate, not actionable)

### Anchored Predicate
An asset is "anchored" if it has ANY of:
- IdP match (SSO/SCIM/service principal)
- CMDB match
- Recurring finance spend
- Cloud resource presence

### Shadow Asset
- **ungoverned** (no IdP AND no CMDB)
- AND **NOT financially_anchored** (no ongoing/recurring finance contract)
- AND **activity_status == RECENT**

**Financial Anchoring Exclusion**: If an asset is ungoverned (NO_IDP + NO_CMDB) but has HAS_ONGOING_FINANCE, it is NOT shadow. Instead, it gets tagged with `FINANCIAL_ANCHOR_GOVERNANCE_GAP` (onboarding queue, not shadow triage).

*Interpretation: "We know this software is actively used, but it's not being managed through official channels."*

### Financially Anchored, Governance Gap
- **ungoverned** (no IdP AND no CMDB)
- AND **HAS_ONGOING_FINANCE** (active contract exists)
- AND **activity_status == RECENT**

This is NOT shadow IT. It's procurement-known but not access-integrated. Tagged with:
- `SHADOW_EXCLUDED_BY_ONGOING_FINANCE`
- `FINANCIAL_ANCHOR_GOVERNANCE_GAP`

*Interpretation: "Procurement is tracking this, but SSO/CMDB onboarding is needed."*

### Zombie Asset
- **anchored** (IdP OR CMDB OR finance OR cloud)
- AND **activity_status == STALE**

*Interpretation: "This is anchored in our official systems but has stale activity - candidate for deprovision."*

### Parked Asset (NEW Dec 2025)
- **NOT anchored** (ungoverned)
- AND **activity_status == STALE**

*Interpretation: "Ungoverned + stale = non-actionable. Can't deprovision what isn't managed. Not counted as zombie."*

### Key Rule
- `NO_ACTIVITY_TIMESTAMPS` = indeterminate, NOT stale. Cannot be zombie, shadow, or parked without evidence.

## Traffic Light Provisioning
A fail-closed asset provisioning system that controls flow to DCL:
- **ACTIVE** (Green): Trusted, has IdP or CMDB governance → flows to DCL
- **REVIEW** (Amber): Needs cleanup, CMDB but stale activity → blocked
- **QUARANTINE** (Red): Shadow IT, no governance → blocked
- **BLOCKED**: Explicitly banned → blocked
- **RETIRED**: Decommissioned → blocked
- **IGNORED**: Hard rejection (invalid TLD, infrastructure) → dropped

## Gatekeeper Triage UI
Workflow-oriented triage with three color-coded sections:
- **Red (Firewall)**: `QUARANTINE` shadow IT, actions: Approve, Ban. High-value shadows (FINANCE_GAP) sorted first with ($) badge.
- **Yellow (Risk)**: `REVIEW` zombies + `ACTIVE` with identity_gap (toxic assets), actions: Deprovision, Sanction, Dismiss Risk.
- **Green (Hygiene)**: `ACTIVE` with other findings (CMDB gap, governance gap, data conflict), actions: Acknowledge, Assign Owner.

## Farm Reconciliation

### Design Principle
- Farm owns reconciliation UI (has expected + actual + diffs)
- AOD owns its structured "actual" output only
- **HARD RULE: AOD NEVER consumes Farm expected/rca data. AOD ONLY emits its own "actual + reasons".**

### Contract Invariants
1. **Zero blank reason codes** - Every asset summary MUST have non-empty `aod_reason_codes`
2. **Zero KEY_NORMALIZATION_MISMATCH** - If evidence contains a registered domain, the key MUST be that domain
3. **Lists derived from summaries** - `shadow_asset_keys` and `zombie_asset_keys` are derived from summaries (single source of truth)

### Canonical Reason Codes
- `HAS_IDP`, `NO_IDP` - IdP presence
- `HAS_CMDB`, `NO_CMDB` - CMDB presence
- `HAS_FINANCE`, `NO_FINANCE` - Finance evidence
- `HAS_CLOUD`, `NO_CLOUD` - Cloud evidence
- `HAS_DISCOVERY`, `NO_DISCOVERY` - Discovery evidence
- `RECENT_ACTIVITY`, `STALE_ACTIVITY`, `NO_ACTIVITY_TIMESTAMPS` - Activity status
- `DISCOVERY_SOURCE_COUNT_GE_2`, `DISCOVERY_SOURCE_COUNT_LT_2` - Discovery source count

## UI Design
Uses AutonomOS palette:
- Primary accent: Cyan (#0bcad9, #22d3ee)
- Secondary accent: Purple (#a855f7)
- Dark foundation: Slate-900/950
- Font: Quicksand

## Quality Guardrails

### Definition of "DONE"
A change is DONE only if it meets all 4:
1. **Semantics preserved** - Behavior matches stated IRL meaning
2. **No cheating** - No overwrites, optional-everything, silent fallbacks, or ground-truth labels
3. **Proof is real** - Tests alone are not proof; show before/after output from a real run
4. **Negative test included** - Ensure the cheat can't come back

### Fail Loudly
When data is bad or missing, do NOT "handle" it by pretending it's fine. Use explicit error statuses and surface the reason.

## Running the Application
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

## Running Tests
```bash
pytest tests/ -v
```

## Lens Match Debug (CMDB/IdP Diagnostics)

The `lens_match_debug` field provides diagnostic information for CMDB/IdP/Cloud/Finance matching, helping identify why matches might be incorrect:

```json
{
  "lens_match_debug": {
    "cmdb": {
      "match_method": "domain",      // How the match was made
      "match_key": "box.com",        // Key used for matching
      "matched_record_id": "CI596977", // CMDB record ID
      "matched_record_name": "Box",  // CMDB record name
      "ambiguity_code": "NONE",      // NONE, UNRESOLVED, or FIRST_WINS
      "disambiguation_detail": null  // Why disambiguation was needed
    },
    "idp": { ... },
    "cloud": null,
    "finance": { ... }
  }
}
```

**Match Methods** (reliability order):
1. `domain` - Highest confidence (exact domain match)
2. `canonical_name` - High confidence (normalized name match)
3. `uri` - Medium confidence (URL-based match)
4. `fuzzy` - Lower confidence (fuzzy string matching)
5. `vendor_fallback` - Lowest confidence (matched via vendor only)

**Ambiguity Codes**:
- `NONE` - Single clear match
- `FIRST_WINS` - Multiple candidates, first was selected
- `UNRESOLVED` - Multiple candidates, no clear winner

## Performance Optimizations (Dec 2025)

### Pipeline Stage Timing
- Added `PipelineStageTimings` model tracking 10 stages: fetch_snapshot, validate_snapshot, normalize, build_indexes, correlate, artifacts, admission, findings, persist, total
- Timing stored in `runs.stage_timings` JSON column and exposed via API
- Dashboard header shows "Last Run: X.XXs" in top right corner
- Each run in Discovery Runs list shows timing badge (e.g., "2.3s")

### Correlation Performance
- Pre-computed fuzzy indexes at build_plane_indexes time to eliminate O(n×m) loops
- New PlaneIndex fields: `by_name_prefix`, `by_name_bigrams`, `by_name_words`
- Fuzzy/contains matching now uses O(1) lookups with fallback to original loops

## Known Issues (Current Status)
*   **CMDB Debug Fields Missing**: ✅ FIXED (Dec 2025) - The `lens_match_debug` field was not being saved in batch inserts. Now correctly populated for all assets.
*   **Admission Noise Floor Bug**: ✅ FIXED (Dec 2025) - Discovery admission now counts distinct **sources** (browser, proxy, dns = 3) instead of planes. Assets like asana.com with 3 network sources are now correctly admitted. Plane diversity retained as annotation (`PLANE_DIVERSITY_GE_2`/`PLANE_DIVERSITY_LT_2`).
*   **Key Normalization Mismatch**: ✅ FIXED (Dec 2025) - Reconcile payload now emits `domain_aliases`, `registered_domain`, and `domain_alias_map` for Farm to match against any key variant. KEY_NORMALIZATION_MISMATCH = 0 verified.
*   **Pipeline Performance Optimized**: ✅ FIXED (Dec 2025) - Correlation O(n×m) loops replaced with pre-computed fuzzy indexes for O(1) lookups. Timing instrumentation added for all pipeline stages.

## Documentation
*   **docs/AOD_DISCOVER_LOGIC.md**: Executive summary of discovery logic, lifecycle, admission gates, classifications, traffic light provisioning, and findings.
*   **docs/DISCOVERY_LOGIC_TECHNICAL.md**: Technical details on pipeline stages, entity normalization, CMDB/IdP correlation methods, matching strategies, and reason codes.
*   **docs/aod-admission-policy.md**: Detailed admission policy with pipeline stages, gate criteria, and example traces.
*   **docs/policy-engine-refactoring-plan.md**: Refactoring plan for configuration-driven policy engine.
*   **docs/guided-validation-tour-script.md**: Script and phases for the guided validation tour.
