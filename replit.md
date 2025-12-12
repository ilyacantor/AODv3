# AOD Discover v3

## Overview
AOD Discover v3 is an enterprise-grade microservice for automated IT asset discovery, Shadow IT detection, and risk-based triage workflows. It's part of the larger AOS platform, combining rule-based logic with planned machine learning to create a master catalog of IT assets.

## Tech Stack
- **Backend**: Python 3.11, FastAPI, Uvicorn
- **Database**: PostgreSQL (Supabase)
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **HTTP Client**: httpx for Farm API calls

## Project Structure
```
├── main.py                 # FastAPI application entry point
├── src/aod/
│   ├── config.py          # Configuration from environment
│   ├── db.py              # Database connection helpers (asyncpg)
│   ├── farm_client.py     # Farm API HTTP client
│   ├── models.py          # Pydantic models
│   ├── lifecycle.py       # Lifecycle routing & findings logic
│   ├── ingest_service.py  # Asset ingestion pipeline
│   ├── dashboard_service.py # Dashboard queries
│   └── migrate.py         # Database migration runner
├── migrations/            # SQL migration files
├── templates/             # Jinja2 HTML templates
└── static/                # CSS and JavaScript
```

## Key Concepts

### Lifecycle States (V1 Full-Pull Model)
- **DISCOVERED**: Total assets count metric (all assets regardless of end state)
- **PARKED**: Blocked by critical issues - requires HITL intervention
- **CATALOGED**: Validated and ready for use

### Blocking Rules (PARKED)
- `SOR_CONFLICT`, `ONT_SOR_CONFLICT` → SoR Conflict
- `SCHEMA_MISMATCH`, `SCHEMA_OR_SHAPE_MISMATCH`, `DATA_SCHEMA_DRIFT`, `ONT_AMBIGUOUS_TYPE` → Schema Mismatch
- `ID_COLLISION` → ID Collision
- `MISSING_PRIMARY_ID` → Missing ID

### Finding Types (Multi-Label)
Findings are additive - one asset can trigger multiple findings:
- **shadow_it**: Unauthorized/unmanaged applications
- **governance_gap**: Missing ownership or unmapped vendor
- **data_conflicts**: Data quality issues detected
- **ops_risk**: High anomaly score (≥0.4)
- **low_confidence**: Low classification confidence (<0.5)

### Farm Bucket Classification (Mutually Exclusive)
Persisted directly from Farm's classification - each asset belongs to exactly one bucket:
- **clean**: No issues detected
- **non_blocking**: Has findings but not blocked
- **blocking**: Parked due to critical issues
- **shadow**: Shadow IT assets

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (required)
- `FARM_URL`: Farm API base URL (optional, defaults to example)

## API Endpoints
- `GET /` - Dashboard UI
- `GET /triage` - Triage center UI
- `GET /catalogs` - Catalog run history UI
- `GET /health` - Health check
- `GET /api/dashboard` - Dashboard data JSON
- `GET /api/assets/lifecycle/{state}` - Assets by lifecycle
- `GET /api/assets/parked/{reason}` - Assets by parked reason
- `GET /api/assets/finding/{type}` - Assets by finding type
- `GET /api/assets/shadow-it` - All Shadow IT assets
- `GET /api/assets/inventory/{field}/{value}` - Assets by inventory field
- `GET /api/assets/shadow-it/{field}/{value}` - Shadow IT by field
- `GET /api/assets/{id}` - Asset detail
- `GET /api/ingest/runs` - Get all catalog runs
- `POST /api/farm/ingest` - Trigger Farm ingestion
- `POST /api/reset` - Reset all assets and findings (preserves catalog history)
- `GET /validation` - Validation page UI (Farm bucket counts)
- `GET /api/validation/buckets` - Farm bucket counts JSON
- `GET /api/validation/metrics` - Validation metrics JSON

## Running Locally
```bash
python main.py
```

## Recent Changes
- **Dec 12, 2025**: Added farm_bucket column for Farm's mutually exclusive bucket classification (clean, non_blocking, blocking, shadow)
- **Dec 12, 2025**: Created Validation page showing Farm's exclusive bucket counts with clear labeling
- **Dec 12, 2025**: Updated Dashboard/Triage to show "X assets / Y findings" format for multi-label findings
- **Dec 12, 2025**: Fixed Shadow IT to count across ALL lifecycle states (PARKED + CATALOGED)
- **Dec 12, 2025**: Added "Reset All Data" button and Catalogs tab with full run history (company name, archetype, scale, duration, all counts)
- **Dec 12, 2025**: Enhanced findings display with detailed evidence (shadow reasons, conflict types, anomaly scores, confidence levels)
- **Dec 12, 2025**: Stage 2 complete - Real Farm contract, canonical lifecycle router, findings generation, reconciled dashboard counts
- **Dec 12, 2025**: Added clickable bar charts for inventory drill-down
- **Dec 12, 2025**: Initial v3 rewrite with simplified architecture
