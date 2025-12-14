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

## Recent Changes

- Contract-driven Farm adapter with explicit mapping tables
- 17 contract tests verifying all planes normalize correctly
- Real Farm snapshot fixture for integration testing
- Tenant dropdown auto-loads on page open
- Updated `/api/runs/from-farm` to persist run provenance
- Pipeline uses `COMPLETED_WITH_RESULTS` / `COMPLETED_NO_ASSETS`
- FarmClient has `list_snapshots()` method
