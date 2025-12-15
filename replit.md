# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS, an enterprise operating system. It ingests raw enterprise evidence from AOS Farm and produces:

- **Asset Catalog** - Systems only (not internal objects like dashboards)
- **Run Log** - Audit trail of what happened on each run
- **Explainable Findings** - Rule-based findings with no anomaly scores or ML

The system is designed to be deterministic (same input yields same output), evidence-only (no pre-adjudicated labels), and fully explainable.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles

1. **No Ground Truth Ingestion** - Rejects banned fields like `is_shadow_it`, `ground_truth`, `inCMDB`. If present, marks run as `INVALID_INPUT_CONTRACT`
2. **No ML/Anomaly Scores** - Only deterministic rules and explainable correlation
3. **Deterministic** - Same snapshot + same config produces identical outputs with stable ordering
4. **Evidence-Only Decisions** - Admission and findings derived only from plane evidence, never upstream labels
5. **Assets vs Artifacts** - Systems are assets; internal objects (dashboards, reports) are artifacts and don't inflate asset counts

### Pipeline Architecture

The discovery pipeline runs in 7 sequential stages:

| Stage | Module | Purpose |
|-------|--------|---------|
| 1 | `validate_snapshot.py` | Schema validation, banned field rejection |
| 2 | `normalize_observations.py` | Normalize names/domains, derive candidate entities |
| 3 | `build_plane_indexes.py` | Build indexes for efficient correlation |
| 4 | `correlate_entities.py` | Three-pass correlation across planes |
| 5 | `admission.py` | Apply admission criteria to determine assets |
| 6 | `artifact_handler.py` | Identify and record artifacts |
| 7 | `findings_engine.py` | Generate deterministic findings |

### Data Planes

Evidence comes from 7 planes that represent different enterprise data sources:

- **Discovery** - Network observations (DNS, proxy, endpoint)
- **IdP** - Identity provider data (SSO, SCIM, service principals)
- **CMDB** - Configuration management database
- **Cloud** - Cloud resource inventory
- **Endpoint** - Device and installed app data
- **Network** - DNS records, proxy logs, certificates
- **Finance** - Vendors, contracts, transactions

### Derived Classifications

Shadow and Zombie classifications are computed post-pipeline as views, not stored flags:

- **Shadow Asset** - Has activity evidence but no IdP or CMDB match
- **Zombie Asset** - Has IdP/CMDB presence but no recent activity (30-day window)

### Identity vs Evidence Contract

**IDENTITY (required, canonical):**
- `vendor_key`: Internal canonical vendor ID. Stable, source-agnostic, deterministic.
  - Normalization: lowercase, alphanumeric only, no TLD
  - Example: `yammer`, `hipchat`, `pivotaltracker`
  - This is the ONLY field used for reconciliation and matching

**EVIDENCE (optional, variable):**
- `domain_key`: Legacy `*com` format for backward compatibility (e.g., `yammercom`)
- `domains[]`: Actual domain evidence if known (e.g., `["yammer.com"]`)
- `display_name`: Human-readable name (e.g., `Yammer`, `PIVOTAL TRACKER`)

**RECONCILIATION CONTRACT:**
- AOD MUST always emit `vendor_key` for every zombie/shadow asset
- Farm MUST compare on `vendor_key` only
- `domain_key` is temporary fallback for backward compat (to be deprecated)

### API Structure

FastAPI application with these key endpoints:

- `POST /api/runs/from-farm` - Trigger discovery run from Farm snapshot
- `GET /api/runs/{run_id}` - Get run details
- `GET /api/runs/{run_id}/assets` - Get assets for a run
- `GET /api/runs/{run_id}/findings` - Get findings for a run
- `GET /api/farm/snapshots` - Proxy to Farm for snapshot listing
- `POST /api/debug/zombie-explain` - Debug endpoint for zombie classification explanations
- `POST /api/debug/zombie-reconcile` - Reconcile zombie classifications against Farm expectations

### Run Status Semantics

Runs must return one of these explicit statuses:
- `UPSTREAM_ERROR` - Farm unreachable or HTTP error
- `INVALID_SNAPSHOT` - Schema mismatch or wrong version
- `INVALID_INPUT_CONTRACT` - Banned fields present
- `COMPLETED_NO_ASSETS` - Pipeline completed, nothing admitted
- `COMPLETED_WITH_RESULTS` - Normal success with assets/findings

### Database Design

SQLite persistence layer structured for future PostgreSQL migration. Key tables:
- `runs` - Run logs with status and counts
- `assets` - Admitted assets with lens statuses
- `findings` - Generated findings linked to assets
- `artifacts` - Non-system objects
- `run_observation_samples` - Capped observation samples per run
- `run_ambiguous_matches` - Ambiguous correlation groups
- `run_rejections` - Rejected candidates with reasons

IDs are run-scoped using deterministic UUID generation from snapshot + content components.

## External Dependencies

### AOS Farm

Farm is the upstream evidence source. AOD fetches snapshots via HTTP:

- `FARM_URL` environment variable (required) - Base URL for Farm API
- `FARM_SHARED_SECRET` environment variable (optional) - Auth header for reconciliation
- `GET {FARM_URL}/api/snapshots?tenant_id=<tenant>&limit=20` - List snapshots
- `GET {FARM_URL}/api/snapshots/{snapshot_id}` - Fetch full snapshot
- `POST {FARM_URL}/api/reconcile` - Auto-sync run results back to Farm

Snapshots must have `meta.schema_version == "farm.v1"`. The `farm_adapter.py` module normalizes Farm wire format to AOD canonical schema.

### Farm Auto-Sync

After a successful pipeline run from Farm, AOD automatically reconciles results back:

- **Sync Status** - Tracked per run: `pending`, `synced`, `failed`, `not_applicable`
- **Reconcile Payload** - Includes counts, shadow/zombie asset lists, high-severity findings
- **UI Display** - Sync status badges shown on run list items (green=synced, red=failed, cyan=syncing)
- **Error Handling** - Graceful handling of HTTP errors, connection errors, timeouts with error messages stored

### Python Dependencies

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation and serialization
- **aiosqlite** - Async SQLite database
- **httpx** - Async HTTP client for Farm communication

### Frontend

Single-page application served from `templates/index.html`:
- Quicksand font family
- AutonomOS color palette (cyan/purple/semantic colors)
- Dropdown snapshot picker (no free-text Farm URL entry)
- Drillable KPI cards with normalized view-models