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

### Lifecycle States
- **DISCOVERED**: Initial state when asset is first seen
- **PARKED**: Blocked by critical issues (SoR Conflict, Schema Mismatch, ID Collision, Missing ID)
- **CATALOGED**: Validated and ready for use

### Finding Types (Non-Blocking)
- **shadow_it**: Unauthorized/unmanaged applications
- **governance_gap**: Missing ownership or unmapped vendor
- **data_conflicts**: Data quality issues detected
- **ops_risk**: High anomaly score (≥0.4)
- **low_confidence**: Low classification confidence (<0.5)

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (required)
- `FARM_URL`: Farm API base URL (optional, defaults to example)

## API Endpoints
- `GET /` - Dashboard UI
- `GET /triage` - Triage center UI
- `GET /health` - Health check
- `GET /api/dashboard` - Dashboard data JSON
- `GET /api/assets/lifecycle/{state}` - Assets by lifecycle
- `GET /api/assets/parked/{reason}` - Assets by parked reason
- `GET /api/assets/finding/{type}` - Assets by finding type
- `GET /api/assets/{id}` - Asset detail
- `POST /api/farm/ingest` - Trigger Farm ingestion

## Running Locally
```bash
python main.py
```

## Recent Changes
- **Dec 12, 2025**: Initial v3 rewrite with simplified architecture
