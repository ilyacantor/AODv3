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

### Shadow Asset
- Has activity evidence (Finance, Cloud, or Discovery)
- AND no IdP match (no SSO / SCIM / service principal)
- AND no CMDB match
- AND has **recent activity** within 90 days

*Interpretation: "We know this software is actively used, but it's not being managed through official channels."*

### Zombie Asset
- CMDB or IdP presence (officially managed)
- AND (**no activity timestamps** OR activity **outside 90-day window**)

*Interpretation: "This is in our official systems but we have no evidence anyone is actually using it."*

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

## Known Issues (Current Status)
*   **Admission Noise Floor Bug**: Discovery admission counts distinct **planes** instead of distinct **sources**. Assets with 3 discovery sources (browser, proxy, dns) all mapping to `network` plane get rejected despite meeting the ≥2 sources policy. Fix: Change `check_discovery_admission()` to count sources, not planes.
*   **Key Normalization Mismatch**: Domain canonicalization upgrades keys (e.g., `app.asana.com` → `asana.com`) but Farm reconciliation expects original keys, causing KEY_NORMALIZATION_MISMATCH errors. Fix: Emit alias metadata or update reconciliation to use canonical keys.

## Documentation
*   **docs/AOD_DISCOVER_LOGIC.md**: Executive summary of discovery logic, lifecycle, admission gates, classifications, traffic light provisioning, and findings.
*   **docs/DISCOVERY_LOGIC_TECHNICAL.md**: Technical details on pipeline stages, entity normalization, CMDB/IdP correlation methods, matching strategies, and reason codes.
*   **docs/aod-admission-policy.md**: Detailed admission policy with pipeline stages, gate criteria, and example traces.
*   **docs/policy-engine-refactoring-plan.md**: Refactoring plan for configuration-driven policy engine.
*   **docs/guided-validation-tour-script.md**: Script and phases for the guided validation tour.
