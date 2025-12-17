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
| 4 | `correlate_entities.py` | Four-pass correlation with disambiguation |
| 5 | `admission.py` | Apply admission criteria to determine assets |
| 6 | `artifact_handler.py` | Identify and record artifacts |
| 7 | `findings_engine.py` | Generate deterministic findings |

### Correlation Disambiguation

When multiple matches occur during correlation, the system attempts to disambiguate using these codes:

| Code | Meaning | Resolution |
|------|---------|------------|
| `NONE` | Single clear match | MATCHED |
| `MULTI_ENV` | Same app in dev/staging/prod CIs | MATCHED (pick prod) |
| `LEGACY` | Old/deprecated CI alongside current | MATCHED (pick current) |
| `DUPLICATE` | True duplicate records | MATCHED (pick first) |
| `PARENT_VENDOR` | Matched parent vendor, not product | **UNMATCHED** |
| `UNRESOLVED` | Could not disambiguate | AMBIGUOUS |

**Evidence-Driven Resolution Principle:** Disambiguation resolves ONLY when CMDB fields support it; otherwise keeps AMBIGUOUS with reason=UNRESOLVED.

| Code | Required Evidence |
|------|-------------------|
| `MULTI_ENV` | `environment` or `environment_type` field differs between records |
| `LEGACY` | `status`, `is_deprecated`, or `lifecycle_state` indicates deprecated |
| `DUPLICATE` | Records have identical `name`, `vendor`, and `app_type` fields |

**PARENT_VENDOR Prevention:** When vendor-only matching finds multiple products from the same vendor (e.g., Trello matching Confluence+Hipchat via "Atlassian"), the match is rejected as UNMATCHED.

**Substring False Positive Prevention:** Contains matching uses `KNOWN_DISTINCT_PRODUCTS` blocklist to prevent false matches like "box"→"dropbox", "git"→"github", etc.

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
- `POST /api/debug/aod-agent-reconcile` - AOD Agent diagnostic reconciliation (actual results + RCA codes)
- `POST /api/reconcile/explain-nonflag` - Explain why specific assets are NOT in shadow/zombie lists
- `GET /api/runs/{run_id}/reconcile-payload` - Get the exact payload that would be sent to Farm (uses shared helper)
- `POST /api/runs/resync` - Re-trigger Farm callback for existing run (for debugging/verification)

### AOD Actual Results Emitter

**DESIGN PRINCIPLE (prevents coupling):**
- Farm owns reconciliation UI (has expected + actual + diffs)
- AOD owns its structured "actual" output only
- Farm displays side-by-side and runs the RCA reducer
- **HARD RULE: AOD NEVER consumes Farm expected/rca data. AOD ONLY emits its own "actual + reasons".**

**Data Flow:**
- AOD publishes: `shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`
- Farm already has: `shadow_expected`, `zombie_expected`, `expected_reason_codes`
- Farm computes: `extra`, `missed`, `rca_code` per mismatch

**AOD Outputs:**
- `shadow_actual[]` - Assets classified as shadow
- `zombie_actual[]` - Assets classified as zombie
- `admission_actual[key]` - "admitted" | "rejected"
- `actual_reasons[key]` - Canonical reason codes
- `asset_details[key]` - Per-asset evidence summary

**Canonical Reason Codes (emitted by AOD):**
- `HAS_IDP`, `NO_IDP` - IdP presence
- `HAS_CMDB`, `NO_CMDB` - CMDB presence
- `HAS_FINANCE`, `NO_FINANCE` - Finance evidence
- `HAS_CLOUD`, `NO_CLOUD` - Cloud evidence
- `HAS_DISCOVERY`, `NO_DISCOVERY` - Discovery evidence
- `RECENT_ACTIVITY`, `STALE_ACTIVITY`, `NO_ACTIVITY_TIMESTAMPS` - Activity status
- `DISCOVERY_SOURCE_COUNT_GE_2`, `DISCOVERY_SOURCE_COUNT_LT_2` - Discovery source count
- `NO_REASON_DATA` - Fallback when no other reason codes apply (contract invariant: never blank)

**Contract Invariants:**
1. **Zero blank reason codes** - Every `asset_summaries[key].aod_reason_codes` MUST be non-empty
2. **Zero KEY_NORMALIZATION_MISMATCH** - If evidence contains a registered domain, the key MUST be that domain
3. **Lists derived from summaries** - `shadow_asset_keys` and `zombie_asset_keys` are derived from `asset_summaries.is_shadow/is_zombie` flags (single source of truth)

**Payload Contract (v2):**
```json
{
  "payload_version": 2,
  "has_asset_summaries": true,
  "asset_summaries_count": N,
  "asset_summaries": { "<key>": { "aod_decision": "...", "aod_reason_codes": [...], ... } },
  "shadow_asset_keys": [...],  // derived from asset_summaries.is_shadow
  "zombie_asset_keys": [...]   // derived from asset_summaries.is_zombie
}
```

**RCA Reducer (owned by Farm, not AOD):**
Farm uses these codes to determine root cause of mismatches:
- `ACTIVITY_TIMESTAMP_DROPPED` - Farm says recent, AOD says stale
- `DISCOVERY_SOURCE_COUNT_MISMATCH` - Discovery source count differs

### Domain-Keyed Asset Aggregation

**INVARIANT:** When any evidence contains a registered domain (from discovery URLs, proxy logs, finance vendor domains, or vendor name lookup), the asset_key MUST be that registered domain.

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

**Domain-Level Aggregation:**
Multiple assets sharing the same domain key are merged:
- `is_shadow`/`is_zombie`: OR semantics (if any variant is shadow, domain is shadow)
- `reason_codes`: union of all variant codes
- `aliases`: list of source asset names for traceability

**Example:**
- `Notion (Legacy)` + `Notion-prod` → Both roll up under `notion.so`
- `aliases: ["Notion (Legacy)", "Notion-prod"]`

**Canonical Flag Tracking:**
Only assets with `is_domain_canonical=True` are counted in shadow/zombie stats:
- Domain-keyed assets (from steps 1-4) → canonical, counted
- Name-derived fallbacks (step 5) → NOT canonical, excluded from counts

This eliminates KEY_NORMALIZATION_MISMATCH errors in Farm reconciliation by ensuring AOD and Farm use the same canonical domain keys.

### Explain Non-Flag Endpoint

`POST /api/reconcile/explain-nonflag` - Farm can ask AOD why specific assets are NOT flagged as shadow/zombie.

**Request:**
```json
{
  "snapshot_id": "uuid",
  "asset_keys": ["Salesforce", "HubSpot"],
  "ask": "shadow" | "zombie" | "both"
}
```

**Response (per key):**
```json
{
  "asset_key": "Salesforce",
  "present_in_aod": true,
  "decision": "admitted_not_shadow",
  "reason_codes": ["HAS_IDP", "HAS_CMDB", "RECENT_ACTIVITY"],
  "primary_reason": "HAS_IDP"
}
```

**Decision Types:**
- `unknown_key` - AOD never saw this asset (no candidate formed)
- `not_admitted` - Saw it but rejected (no admission gate satisfied)
- `admitted_not_shadow` - Admitted, but has presence evidence (not shadow)
- `admitted_not_zombie` - Admitted, but has recent activity (not zombie)

**Guardrail:** Farm only sends keys + snapshot_id + ask-type. AOD does NOT consume any expected data.

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