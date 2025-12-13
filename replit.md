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
│   ├── breaches.py        # Observed Breach Ledger taxonomy & evidence gates
│   ├── ingest_service.py  # Asset ingestion pipeline
│   ├── dashboard_service.py # Dashboard queries
│   ├── ledger_service.py  # Run-scoped breach queries for Farm grading
│   └── migrate.py         # Database migration runner
├── migrations/            # SQL migration files
├── templates/             # Jinja2 HTML templates
├── static/                # CSS and JavaScript
├── tests/                 # Unit tests
└── docs/                  # Documentation (defect dictionary)
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
- `GET /api/assets/inventory?field=X&key=Y` - Assets by inventory field (preferred, uses stable keys)
- `GET /api/assets/inventory/{field}/{value}` - DEPRECATED: Assets by inventory field (path params)
- `GET /api/assets/shadow-it/{field}/{value}` - Shadow IT by field
- `GET /api/assets/{id}` - Asset detail
- `GET /api/ingest/runs` - Get all catalog runs
- `POST /api/farm/ingest` - Trigger Farm ingestion
- `POST /api/reset` - Reset all assets and findings (preserves catalog history)
- `GET /api/runs` - All runs with breach summary
- `GET /api/runs/{run_id}/observed-breaches` - Observed breaches for Farm grading
- `GET /api/runs/{run_id}/observed-breaches/summary` - Breach summary counts

## Running Locally
```bash
python main.py
```

## Observed Breach Ledger

Contract-grade breach taxonomy with evidence gates. No anomaly_score in contract outputs.

### Blocking Breaches (BLOCKER)
| Breach ID | Name | Source Rules |
|-----------|------|--------------|
| B-ONT-001 | SOR_CONFLICT_CRITICAL_FIELD | SOR_CONFLICT, ONT_SOR_CONFLICT |
| B-DATA-001 | SCHEMA_DRIFT_BREAKING | SCHEMA_MISMATCH, SCHEMA_OR_SHAPE_MISMATCH, DATA_SCHEMA_DRIFT |
| B-ID-001 | ID_COLLISION | ID_COLLISION |
| B-ID-002 | MISSING_REQUIRED_ID | MISSING_PRIMARY_ID |

### Non-Blocking Breaches (NON_BLOCKING)
| Breach ID | Name | Evidence Required |
|-----------|------|-------------------|
| S-SHADOW-001 | OBSERVED_NOT_REGISTERED | presence_source AND absence_source |
| S-GOV-001 | MISSING_OWNER | missing_fields |
| S-DATA-001 | NONBLOCKING_CONFLICT | conflict_types |

### Evidence Gates (Fail Closed)
All evidence gates fail closed - breaches are NOT emitted without concrete evidence.
- **Shadow IT**: Requires BOTH presence evidence (browser_history/billing_records) AND absence evidence (not in IdP/CMDB)
- **SoR Conflict**: Requires concrete field_diffs OR conflicting_sots - rule triggers alone are NOT sufficient
- **Schema Drift**: Requires schema-related rule trigger OR parked_reason match
- **Data Conflicts**: Requires conflict_types list

## Evidence-Based Anomaly Detection

AOD no longer accepts numeric anomaly_score from Farm. Instead, it requires concrete anomaly indicators.

### Accepted Indicator Types
- `unusual_access_patterns` - Abnormal user/access counts
- `data_volume_spike` - Unusual data transfer volumes  
- `off_hours_activity` - Activity outside normal business hours
- `auth_fail_storm` - High rate of authentication failures
- `latency_regression` - Performance degradation
- `permission_escalation` - Unexpected privilege changes
- `geo_anomaly` - Access from unusual locations
- `rate_limit_breach` - API rate limit violations

### Risk Score Calculation
- Indicators are validated (must have type, timestamp, evidence)
- Each indicator has severity weights (low/medium/high)
- Risk score compounds: `1 - Π(1 - weight_i)` capped at 1.0
- Stale indicators (>7 days) are ignored
- Thresholds: warn ≥0.35, critical ≥0.7

## Recent Changes
- **Dec 13, 2025**: Replaced numeric anomaly_score with evidence-based anomaly_indicators and deterministic risk scoring
- **Dec 12, 2025**: Strengthened SoR Conflict evidence gate - now requires concrete field_diffs or conflicting_sots (rule trigger + parked_reason alone no longer sufficient)
- **Dec 12, 2025**: Implemented Observed Breach Ledger with evidence gates and run-scoped export endpoint
- **Dec 12, 2025**: Added breach taxonomy (src/aod/breaches.py) mapping findings to standardized breach IDs
- **Dec 12, 2025**: Added GET /api/runs/{run_id}/observed-breaches endpoint for Farm grading
- **Dec 12, 2025**: Added 44 unit tests for breach mapper, evidence gates, ground truth parsing, and output schema
- **Dec 12, 2025**: Fixed route ordering - specific routes (inventory, shadow-it) now declared before wildcard {asset_id} route
- **Dec 12, 2025**: Added robust vendor drilldown using query params (/api/assets/inventory?field=vendor&key=...) to handle special characters
- **Dec 12, 2025**: Added farm_bucket column for Farm's mutually exclusive bucket classification (clean, non_blocking, blocking, shadow)
- **Dec 12, 2025**: Updated Dashboard/Triage to show "X assets / Y findings" format for multi-label findings
- **Dec 12, 2025**: Fixed Shadow IT to count across ALL lifecycle states (PARKED + CATALOGED)
- **Dec 12, 2025**: Added "Reset All Data" button and Catalogs tab with full run history (company name, archetype, scale, duration, all counts)
- **Dec 12, 2025**: Enhanced findings display with detailed evidence (shadow reasons, conflict types, anomaly scores, confidence levels)
- **Dec 12, 2025**: Stage 2 complete - Real Farm contract, canonical lifecycle router, findings generation, reconciled dashboard counts
- **Dec 12, 2025**: Added clickable bar charts for inventory drill-down
- **Dec 12, 2025**: Initial v3 rewrite with simplified architecture
