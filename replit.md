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

## Recent Changes

- Initial implementation of AOD Fresh
- Complete pipeline with 7 stages
- SQLite persistence layer
- FastAPI REST API
- AOD Console UI with AutonomOS theming
- Comprehensive test suite
