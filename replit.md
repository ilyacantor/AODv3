# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS - an enterprise operating system. It ingests raw enterprise evidence and produces:
- An **Asset Catalog** (systems only; not internal objects like dashboards)
- A **Run Log** (what happened on each run)
- **Explainable findings** (rule-based; no anomaly scores)

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
    │   └── database.py     # SQLite persistence layer
    ├── models/
    │   ├── __init__.py
    │   ├── input_contracts.py   # Pydantic models for snapshot input
    │   └── output_contracts.py  # Pydantic models for assets, findings, etc.
    └── pipeline/
        ├── __init__.py
        ├── validate_snapshot.py      # Stage 1: Schema validation
        ├── normalize_observations.py # Stage 2: Normalize names/domains
        ├── build_plane_indexes.py    # Stage 3: Build plane indexes
        ├── correlate_entities.py     # Stage 4: Three-pass correlation
        ├── admission.py              # Stage 5: Admission criteria
        ├── artifact_handler.py       # Stage 6: Artifact handling
        ├── findings_engine.py        # Stage 7: Generate findings
        └── pipeline_executor.py      # Orchestrate all stages

templates/
└── index.html              # AOD Console UI

tests/
└── test_aod.py             # Test suite
```

## Non-Negotiables

1. **No ground truth ingestion** - Rejects banned fields like `is_shadow_it`, `ground_truth`, `inCMDB`
2. **No ML/anomaly scores** - Only deterministic rules
3. **Deterministic** - Same input yields same output
4. **Evidence-only decisions** - Admission based only on plane evidence
5. **Assets vs Artifacts** - Dashboards/reports/calculators are artifacts, never assets

## Prompt shortcuts

1. **DCCE or dcce** - don't change code, explain

## Tech Stack

- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **SQLite** persistence (structured for PostgreSQL migration)
- **Uvicorn** server

## API Endpoints

- `POST /api/runs` - Create discovery run (file upload)
- `POST /api/runs/json` - Create discovery run (JSON body)
- `POST /api/runs/from-farm` - Create discovery run from Farm HTTP pull
- `GET /api/farm/snapshots?tenant_id=...` - List available snapshots from Farm (proxy)
- `GET /api/runs` - List all runs
- `GET /api/runs/{run_id}` - Get run details
- `GET /api/catalog?run_id=...` - Get assets for run
- `GET /api/findings?run_id=...` - Get findings for run
- `GET /api/artifacts?run_id=...` - Get artifacts for run
- `GET /api/health` - Health check

### Farm HTTP Pull Integration

The `/api/runs/from-farm` endpoint fetches snapshots from an AOS Farm server:

```json
POST /api/runs/from-farm
{
  "tenant_id": "my-tenant",
  "farm_base_url": "https://farm.example.com",
  "snapshot_id": "snapshot-123"
}
```

Validates:
- HTTP status code (must be 2xx, 404 returns explicit "not found" error)
- Content-Type includes JSON (HTML responses rejected with clear error)
- Body is non-empty JSON
- `meta.schema_version == "farm.v1"` (wrong version returns INVALID_INPUT_CONTRACT)

## Running the Application

```bash
python src/main.py
```

Access the UI at http://localhost:5000

## Running Tests

```bash
pytest tests/ -v
```

## UI Design

Uses AutonomOS palette:
- Primary accent: Cyan (#0bcad9, #22d3ee)
- Secondary accent: Purple (#a855f7)
- Dark foundation: Slate-900/950
- Font: Quicksand

## Run Status Values (IRL Semantics)

- `UPSTREAM_ERROR` - Farm unreachable / non-JSON / HTTP error
- `INVALID_SNAPSHOT` - Schema mismatch / wrong version / missing planes  
- `COMPLETED_NO_ASSETS` - Pipeline completed; nothing admitted
- `COMPLETED_WITH_RESULTS` - Normal success with assets
- `COMPLETED` - General success (legacy)
- `FAILED` - Pipeline execution failed
- `INVALID_INPUT_CONTRACT` - Snapshot doesn't conform to input contract

## Farm Snapshot Normalization

The pipeline includes a contract-driven normalization adapter (`src/aod/pipeline/farm_adapter.py`) that transforms raw Farm JSON into canonical AOD schema.

**Validation Flow:** `fetch raw → normalize_farm_snapshot() → Snapshot.model_validate(normalized)`

**Architecture:**
- All field mappings defined in `FIELD_MAPPING` tables (not ad-hoc transformations)
- Separate mapping tables for each record type: META, OBSERVATION, IDP_OBJECT, CMDB_CI, etc.
- Unknown fields preserved in `raw_data` object
- Fails fast with `NormalizationError` and clear missing field messages

**Key Mappings:**
| Farm Wire | Canonical | Plane |
|-----------|-----------|-------|
| `install_id` | `app_id` | endpoint.installed_apps |
| `app_name` | `name` | endpoint.installed_apps |
| `cloud_id` | `resource_id` | cloud.resources |
| `dns_id` | `record_id` | network.dns |
| `proxy_id` | `log_id` | network.proxy |
| `queried_domain` | `domain` | network.dns |
| `observed_name` | `name` | discovery.observations |
| `vendor_hint` | `vendor` | discovery.observations |
| `txn_id` | `transaction_id` | finance.transactions |
| `not_after` | `expires_at` | network.certs |

**Contract Tests:** `tests/test_farm_adapter_contract.py` (17 tests)
**Real Farm Fixture:** `tests/fixtures/real_farm_snapshot.json`

## Derived Classifications

Shadow and Zombie are computed as **derived views** after the main pipeline using **timestamped activity signals** (not stored flags).

### Activity Timestamps

Activity is determined by timestamps from various planes, stored in `asset.activity_evidence`:
- `idp_last_login_at` - Last SSO login
- `discovery_observed_at` - When discovered
- `cloud_observed_at` - Cloud resource observation
- `endpoint_last_seen_at` - Endpoint agent observation
- `network_last_seen_at` - DNS/proxy activity
- `finance_last_transaction_at` - Last financial transaction
- `latest_activity_at` - Max of all above (computed)

### Shadow Asset
- Finance evidence OR cloud presence OR discovery observations
- AND no IdP match (no SSO / SCIM / service principal)
- AND no CMDB match
- AND has **recent activity** within window (default 30 days)

*Interpretation: "We know this software is actively used, but it's not being managed through official channels."*

### Zombie Asset
- CMDB or IdP presence (officially managed)
- AND (**no activity timestamps** OR activity **outside window**)

*Interpretation: "This is in our official systems but we have no evidence anyone is actually using it."*

### Indeterminate
- Shadow candidates with no activity timestamps → indeterminate (can't prove recent use)
- Zombie classification treats missing timestamps as zombie (can't prove usage)

### API
`GET /api/runs/{run_id}/derived?activity_window_days=30`

Returns counts, detailed lists, and **distribution diagnostic**:
- `total_assets`, `with_idp_match`, `with_cmdb_match`
- `with_activity_last_30_days`, `with_any_activity_timestamp`, `indeterminate_count`

**Implementation:** `src/aod/pipeline/derived_classifications.py`
**Tests:** `tests/test_shadow_zombie_timestamps.py` (9 tests)

## Recent Changes

- Added Nuke Prevention Check:
  - `python scripts/nuke_check.py` - fast sanity check (~60 seconds)
  - Verifies FARM_URL, server health, tenant/snapshot access, discovery run, status codes
  - Determinism check: runs same snapshot twice, compares outputs
  - Plain-English PASS/FAIL output with helpful failure diagnostics
  - See README_NUKE_CHECK.md for documentation
- Added Shadow and Zombie derived classifications:
  - Computed on-read from asset evidence (not stored flags)
  - New `/api/runs/{run_id}/derived` endpoint
  - New KPI cards: Shadow Assets (amber), Zombie Assets (red)
  - Drillable with explanations showing why each asset qualifies
  - Help modal updated with Shadow/Zombie definitions
- Added Help modal with plain-English guide:
  - "? Help" button in header opens modal explaining AOD terminology
  - Documents all 6 KPI boxes (Observations, Assets, Artifacts, Findings, Ambiguous, Rejected)
  - Explains drill-down navigation and getting started steps
  - Responsive grid layout for KPI explanations
- Added full drill sets for all 6 KPI boxes:
  - New database tables: observation_samples, ambiguous_matches, rejections
  - Pipeline captures drill data during execution (observations capped at 2000)
  - 3 new API endpoints: /observations, /ambiguous, /rejections (paginated)
  - All 6 stat cards are now clickable and drillable
- Added schema-driven drill-down architecture:
  - DRILL_SCHEMA defines entities (assets, findings, artifacts), fields with defaults, and drill paths
  - normalizeResponse() converts API data to safe view-models with defaults
  - executeDrill() engine handles all drill logic with runtime-discovered paths
  - Clickable KPI cards (Assets, Findings, Artifacts) initiate drill-down
  - Drill panel with breadcrumb navigation and back button
  - Zero-crash guarantee - missing fields, empty arrays handled gracefully
  - Drill stops naturally when result set is 1 or no deeper paths available
- Added snapshot size selector to UI:
  - New "Snapshot Size" dropdown (All sizes, Small, Medium, Large)
  - Size parameter passed to Farm API when listing snapshots
  - Snapshots automatically reload when size selection changes
- Pipeline determinism stabilization:
  - All run identifiers (run_id, started_at) generated at API boundary
  - Pipeline accepts run_id/started_at as required parameters
  - All uuid4() replaced with deterministic_uuid() based on snapshot_id + content hash
  - New determinism test verifies identical outputs across runs
- Contract-driven Farm adapter with explicit mapping tables
- 17 contract tests verifying all planes normalize correctly
- Real Farm snapshot fixture for integration testing
- Tenant dropdown auto-loads on page open
- Updated `/api/runs/from-farm` to persist run provenance
- Pipeline uses `COMPLETED_WITH_RESULTS` / `COMPLETED_NO_ASSETS`
- FarmClient has `list_snapshots()` method
