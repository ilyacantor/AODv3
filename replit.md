# AOD Fresh - Phase 0: Presence Debug

## Overview

AOD Fresh is the discovery module of AutonomOS. **Currently in Phase 0** - stripped down to basic presence verification before reintroducing classification logic.

## Phase 0 Scope

This is a minimal implementation focused on correctness:

- **Debug Endpoint Only** - `/api/debug/presence` shows raw presence per vendor_key
- **No Classifications** - No zombie/shadow heuristics
- **No Reconciliation** - No auto-sync back to Farm
- **No Counts/Labels** - Just raw presence booleans

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check, version v0.1.0-phase0 |
| `GET /api/farm/tenants` | List available tenants from Farm |
| `GET /api/farm/snapshots?tenant_id=X` | List snapshots for a tenant |
| `POST /api/runs/from-farm` | Trigger discovery run from Farm snapshot |
| `GET /api/runs` | List all runs |
| `GET /api/runs/{run_id}` | Get run details |
| `GET /api/catalog?run_id=X` | Get assets for a run |
| **`GET /api/debug/presence?run_id=X`** | **Phase 0 debug table** |

## Debug Presence Endpoint

Returns one row per unique `vendor_key`, aggregated across all assets:

```json
{
  "run_id": "run_abc123",
  "rows": [
    {
      "vendor_key": "slack",
      "in_discovery": true,
      "in_finance": true,
      "in_idp": true,
      "in_cmdb": false,
      "latest_activity_at": "2025-12-15T01:18:46.459862+00:00"
    }
  ]
}
```

### Presence Flags

- **in_discovery**: True if `activity_evidence.discovery_observed_at` is set
- **in_finance**: True if `lens_status.finance == MATCHED`
- **in_idp**: True if `lens_status.idp == MATCHED`
- **in_cmdb**: True if `lens_status.cmdb == MATCHED`
- **latest_activity_at**: Most recent `activity_evidence.latest_activity_at` across all assets with this vendor_key

## Pipeline Architecture

The discovery pipeline runs unchanged from previous versions:

| Stage | Module | Purpose |
|-------|--------|---------|
| 1 | `validate_snapshot.py` | Schema validation, banned field rejection |
| 2 | `normalize_observations.py` | Normalize names/domains, derive candidate entities |
| 3 | `build_plane_indexes.py` | Build indexes for efficient correlation |
| 4 | `correlate_entities.py` | Three-pass correlation across planes |
| 5 | `admission.py` | Apply admission criteria to determine assets |
| 6 | `artifact_handler.py` | Identify and record artifacts |
| 7 | `findings_engine.py` | Generate deterministic findings |

## Data Planes

Evidence comes from 7 planes:

- **Discovery** - Network observations (DNS, proxy, endpoint)
- **IdP** - Identity provider data (SSO, SCIM, service principals)
- **CMDB** - Configuration management database
- **Cloud** - Cloud resource inventory
- **Endpoint** - Device and installed app data
- **Network** - DNS records, proxy logs, certificates
- **Finance** - Vendors, contracts, transactions

## External Dependencies

### AOS Farm

- `FARM_URL` environment variable (required) - Base URL for Farm API
- `GET {FARM_URL}/api/snapshots?tenant_id=<tenant>&limit=20` - List snapshots
- `GET {FARM_URL}/api/snapshots/{snapshot_id}` - Fetch full snapshot

Snapshots must have `meta.schema_version == "farm.v1"`.

## Python Dependencies

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation and serialization
- **aiosqlite** - Async SQLite database
- **httpx** - Async HTTP client for Farm communication

## What Was Removed (Phase 0 Reset)

- `derived_classifications.py` - Zombie/shadow classification logic
- `/api/runs/{run_id}/derived` - Derived classifications endpoint
- `/api/debug/zombie-explain` - Zombie explanation endpoint
- `/api/debug/zombie-reconcile` - Reconciliation debug endpoint
- `/api/debug/timestamp-coverage` - Timestamp coverage analysis
- Farm reconciliation from `POST /api/runs/from-farm`
- Complex UI with stats, drill-down, tabs
