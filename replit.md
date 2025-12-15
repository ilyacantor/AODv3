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
- **Zombie Asset** - Has IdP/CMDB presence but no recent activity (90-day window)

### Vendor Hypothesis (Inference Layer)

Design principle: **Inference decorates reality; it does not redefine it.**

For discovery-only assets, vendor is typically unknown. The system infers a `vendor_hypothesis` from domain patterns:

- **Location**: Normalization layer only (Stage 2)
- **Max confidence**: 0.9 (never authoritative)
- **Basis**: Curated domain-to-vendor mapping (~120 SaaS vendors)
- **Display**: "Likely MongoDB (90% confidence, based on domain:mongodb.com)"

Key constraints:
- `vendor` field remains "unknown" (never overwritten)
- Does NOT affect admission logic
- Does NOT affect shadow/zombie classification
- UI displays inference as suggestion, not fact

**INVARIANT**: `vendor_hypothesis` is NON-DECISIONABLE metadata. It MUST NOT be referenced by admission, classification, findings, policy, scoring, or automation logic.

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

PostgreSQL persistence layer using asyncpg. Single DB selection rule:
- Priority: `SUPABASE_DB_URL` > `DATABASE_URL`
- If neither is set, application fails fast with clear error
- No SQLite fallback or other defaults allowed
- `IGNORE_REPLIT_DB=true` ignores any REPLIT* env vars

Key tables:
- `runs` - Run logs with status and counts
- `assets` - Admitted assets with lens statuses
- `findings` - Generated findings linked to assets
- `artifacts` - Non-system objects
- `observation_samples` - Capped observation samples per run
- `ambiguous_matches` - Ambiguous correlation groups
- `rejections` - Rejected candidates with reasons

IDs are run-scoped using deterministic UUID generation from snapshot + content components.

### Sanity Check

Run `make sanity` to verify storage guardrails:
- PASS if using external DB (SUPABASE_DB_URL or DATABASE_URL)
- FAIL if any local SQLite files exist
- Reports active DB source and ignores REPLIT* vars when IGNORE_REPLIT_DB=true

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
- **asyncpg** - Async PostgreSQL database driver
- **httpx** - Async HTTP client for Farm communication

### Frontend

Single-page application served from `templates/index.html`:
- Quicksand font family
- AutonomOS color palette (cyan/purple/semantic colors)
- Dropdown snapshot picker (no free-text Farm URL entry)
- Drillable KPI cards with normalized view-models