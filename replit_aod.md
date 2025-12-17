# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS - an enterprise operating system. It ingests raw enterprise evidence from AOS Farm and produces:
- An **Asset Catalog** (systems only; not internal objects like dashboards)
- A **Run Log** (audit trail of what happened on each run)
- **Explainable Findings** (rule-based; no anomaly scores or ML)

The system is designed to be deterministic (same input yields same output), evidence-only (no pre-adjudicated labels), and fully explainable.

## Project Architecture

```
src/
├── main.py                 # FastAPI application entry point
└── aod/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes.py       # API endpoints
    ├── db/
    │   ├── __init__.py
    │   └── database.py     # PostgreSQL persistence layer (asyncpg)
    ├── models/
    │   ├── __init__.py
    │   ├── input_contracts.py   # Pydantic models for snapshot input
    │   └── output_contracts.py  # Pydantic models for assets, findings, etc.
    ├── farm_reconcile.py   # Farm auto-sync and reconciliation
    └── pipeline/
        ├── __init__.py
        ├── validate_snapshot.py      # Stage 1: Schema validation
        ├── normalize_observations.py # Stage 2: Normalize names/domains
        ├── build_plane_indexes.py    # Stage 3: Build plane indexes
        ├── correlate_entities.py     # Stage 4: Three-pass correlation
        ├── admission.py              # Stage 5: Admission criteria
        ├── artifact_handler.py       # Stage 6: Artifact handling
        ├── findings_engine.py        # Stage 7: Generate findings
        ├── pipeline_executor.py      # Orchestrate all stages
        ├── derived_classifications.py # Shadow/Zombie computation
        ├── aod_agent_reconcile.py    # Emit actual results for Farm
        ├── vendor_inference.py       # Vendor hypothesis (non-decisionable)
        └── farm_adapter.py           # Farm wire format normalization

templates/
└── index.html              # AOD Console UI

tests/
└── test_*.py               # Test suites
```

## Non-Negotiables

1. **No ground truth ingestion** - Rejects banned fields like `is_shadow_it`, `ground_truth`, `inCMDB`. If present, marks run as `INVALID_INPUT_CONTRACT`
2. **No ML/anomaly scores** - Only deterministic rules and explainable correlation
3. **Deterministic** - Same snapshot + same config produces identical outputs with stable ordering
4. **Evidence-only decisions** - Admission and findings derived only from plane evidence, never upstream labels
5. **Assets vs Artifacts** - Dashboards/reports/calculators are artifacts, never assets; they don't inflate asset counts

## Tech Stack

- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **PostgreSQL** persistence via **asyncpg** (external DB required)
- **Uvicorn** server
- **httpx** for async HTTP to Farm

## Database Configuration

Single DB selection rule (no fallbacks):
- Priority: `SUPABASE_DB_URL` > `DATABASE_URL`
- If neither is set, application fails fast with clear error
- No SQLite fallback or other defaults allowed
- `IGNORE_REPLIT_DB=true` ignores any REPLIT* env vars

Run `make sanity` to verify storage guardrails.

## API Endpoints

### Core Discovery
- `POST /api/runs/from-farm` - Create discovery run from Farm snapshot
- `GET /api/runs` - List all runs
- `GET /api/runs/{run_id}` - Get run details
- `GET /api/runs/{run_id}/assets` - Get assets for a run
- `GET /api/runs/{run_id}/findings` - Get findings for a run
- `GET /api/runs/{run_id}/artifacts` - Get artifacts for a run
- `GET /api/runs/{run_id}/derived` - Get shadow/zombie classifications

### Farm Integration
- `GET /api/farm/snapshots?tenant_id=...` - List available snapshots from Farm (proxy)
- `GET /api/runs/{run_id}/reconcile-payload` - Get the exact payload that would be sent to Farm
- `POST /api/runs/resync` - Re-trigger Farm callback for existing run

### Debug & Reconciliation
- `POST /api/debug/zombie-explain` - Debug endpoint for zombie classification explanations
- `POST /api/debug/zombie-reconcile` - Reconcile zombie classifications against Farm expectations
- `POST /api/debug/aod-agent-reconcile` - AOD Agent diagnostic reconciliation (actual results + RCA codes)
- `POST /api/reconcile/explain-nonflag` - Explain why specific assets are NOT in shadow/zombie lists

### Health
- `GET /api/health` - Health check

## Run Status Values

Runs must return one of these explicit statuses:
- `UPSTREAM_ERROR` - Farm unreachable or HTTP error
- `INVALID_SNAPSHOT` - Schema mismatch or wrong version
- `INVALID_INPUT_CONTRACT` - Banned fields present
- `COMPLETED_NO_ASSETS` - Pipeline completed, nothing admitted
- `COMPLETED_WITH_RESULTS` - Normal success with assets/findings

## Derived Classifications

Shadow and Zombie are computed as **derived views** after the main pipeline using **timestamped activity signals** (not stored flags).

### Shadow Asset
- Has activity evidence (Finance, Cloud, or Discovery)
- AND no IdP match (no SSO / SCIM / service principal)
- AND no CMDB match
- AND has **recent activity** within window (default 90 days)

*Interpretation: "We know this software is actively used, but it's not being managed through official channels."*

### Zombie Asset
- CMDB or IdP presence (officially managed)
- AND (**no activity timestamps** OR activity **outside 90-day window**)

*Interpretation: "This is in our official systems but we have no evidence anyone is actually using it."*

## Farm Reconciliation

### Design Principle (prevents coupling)
- Farm owns reconciliation UI (has expected + actual + diffs)
- AOD owns its structured "actual" output only
- Farm displays side-by-side and runs the RCA reducer
- **HARD RULE: AOD NEVER consumes Farm expected/rca data. AOD ONLY emits its own "actual + reasons".**

### Contract Invariants
1. **Zero blank reason codes** - Every `asset_summaries[key].aod_reason_codes` MUST be non-empty
2. **Zero KEY_NORMALIZATION_MISMATCH** - If evidence contains a registered domain, the key MUST be that domain
3. **Lists derived from summaries** - `shadow_asset_keys` and `zombie_asset_keys` are derived from `asset_summaries.is_shadow/is_zombie` flags (single source of truth)

### Payload Contract (v2)
```json
{
  "payload_version": 2,
  "has_asset_summaries": true,
  "asset_summaries_count": N,
  "asset_summaries": { "<key>": { "aod_decision": "...", "aod_reason_codes": [...], ... } },
  "shadow_asset_keys": [...],
  "zombie_asset_keys": [...]
}
```

### Canonical Reason Codes
- `HAS_IDP`, `NO_IDP` - IdP presence
- `HAS_CMDB`, `NO_CMDB` - CMDB presence
- `HAS_FINANCE`, `NO_FINANCE` - Finance evidence
- `HAS_CLOUD`, `NO_CLOUD` - Cloud evidence
- `HAS_DISCOVERY`, `NO_DISCOVERY` - Discovery evidence
- `RECENT_ACTIVITY`, `STALE_ACTIVITY`, `NO_ACTIVITY_TIMESTAMPS` - Activity status
- `DISCOVERY_SOURCE_COUNT_GE_2`, `DISCOVERY_SOURCE_COUNT_LT_2` - Discovery source count
- `NO_REASON_DATA` - Fallback when no other reason codes apply
- `NOT_RECONCILIATION_ELIGIBLE` - Name-derived key (not domain-keyed)

## Domain-Keyed Asset Aggregation

**INVARIANT:** When any evidence contains a registered domain, the asset_key MUST be that registered domain.

**Key Resolution Order (DOMAIN PROMOTION):**
1. `asset.identifiers.domains` - Explicit domain from evidence
2. `VENDOR_TO_DOMAIN[asset.vendor]` - Reverse lookup from vendor name
3. **NAME-BASED PROMOTION** - Normalize asset name and look up in VENDOR_TO_DOMAIN
4. Asset name if it looks like a domain (contains valid TLD)
5. Fallback: normalized name (for internal systems only) - NOT reconciliation-eligible

**Name Normalization for Vendor Lookup:**
Asset names like "Notion-prod", "Monday.com-Test", "Zapier Integration" are normalized:
- Strip parenthetical content: "Notion (Legacy)" → "notion"
- Strip common suffixes: "-prod", "-dev", "-test", "-staging", "-api", "-integration"
- Match against VENDOR_TO_DOMAIN for canonical domain

## Vendor Hypothesis (Inference Layer)

Design principle: **Inference decorates reality; it does not redefine it.**

For discovery-only assets, vendor is typically unknown. The system infers a `vendor_hypothesis` from domain patterns:

- **Location**: Normalization layer only (Stage 2)
- **Max confidence**: 0.9 (never authoritative)
- **Basis**: Curated domain-to-vendor mapping (~120 SaaS vendors)

**INVARIANT**: `vendor_hypothesis` is NON-DECISIONABLE metadata. It MUST NOT be referenced by admission, classification, findings, policy, scoring, or automation logic.

## Running the Application

```bash
# Start server
python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

Access the UI at http://localhost:5000

## Running Tests

```bash
pytest tests/ -v
```

## Nuke Prevention Check

Run `python scripts/nuke_check.py` to verify pipeline health:
- Verifies FARM_URL, server health, tenant/snapshot access
- Runs discovery pipeline and validates status codes
- Determinism check: runs same snapshot twice, compares outputs
- See `README_NUKE_CHECK.md` for full documentation

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

## Recent Changes

- Payload Contract v2 with `payload_version`, `has_asset_summaries`, `asset_summaries_count` fingerprint fields
- `NO_REASON_DATA` fallback ensures zero blank reason codes
- Lists derived from summaries (single source of truth)
- `/api/runs/resync` endpoint for manual Farm callback re-triggering
- Domain-keyed asset aggregation with name-based promotion
- Vendor hypothesis (non-decisionable inference)
- Farm auto-sync with sync status tracking
