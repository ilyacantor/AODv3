# AOD - AutonomOS Discovery Module

## What is AOD?

AOD (Asset Ownership Discovery) is the **front-end entry point** to the AOS (AutonomOS) platform. It discovers all SaaS applications, cloud services, and software assets in use across an organization, preparing them for connection to the broader AOS data stack.

**Production URL:** `discover.autonomos.tech`

### AOD's Role in AOS

AOD sits at the beginning of the AOS data flow:

```
AOD (Discover) → AAM (Connect) → DCL (Unify) → Agents (Act)
```

| Layer | Component | Purpose |
|-------|-----------|---------|
| **Entry** | AOD | Discover & classify everything running in the estate |
| **Connect** | AAM | Adaptive API Mesh - connection and auth layer |
| **Unify** | DCL | Data Connectivity Layer - canonical ontology |
| **Act** | Agents | Domain-specific AI agents (FinOps, RevOps, etc.) |

### What AOD Does

1. **Discovers** assets from multiple data sources (browser logs, network scans, SSO logs, expense reports)
2. **Prepares for AAM** - identifies which assets need connectors
3. **Classifies** (value-added byproduct) - categorizes assets by governance status (governed, shadow, zombie)
4. **Surfaces findings** that require attention before AAM connection (identity gaps, finance gaps, data conflicts)
5. **Enables triage** so teams can prioritize what to connect first

---

## How AOD Works

### Data Flow Overview

```
Farm (Test Data) → Fetch → Pipeline → Catalog → Triage UI
     ↓
  Snapshots contain:
  - Discovery observations
  - IdP records (SSO)
  - CMDB records
  - Finance transactions
  - Cloud inventory
```

### Core Components

#### 1. Fetch (`/api/farm/*`)
Retrieves snapshot data from Farm (the test data generator). Handles cold-start autoscale with automatic retry and user-friendly loading states.

#### 2. Pipeline (`src/aod/pipeline/`)
Processes raw observations through a 7-stage sequential pipeline:

| Stage | Purpose |
|-------|---------|
| **Validation** | Verify snapshot structure and data integrity |
| **Normalization** | Standardize domains, extract tenant tokens |
| **Indexing** | Build lookup indexes for correlation |
| **Correlation** | Match discovery data to IdP/CMDB/Finance records |
| **Admission** | Apply gates to determine which assets enter catalog |
| **Artifact Handling** | Process findings and classifications |
| **Output** | Generate final catalog with reason codes |

#### 3. Classifications (`src/aod/pipeline/classifications/`)
Determines asset status based on governance signals:

- **Shadow IT**: Assets lacking governance (no IdP, no CMDB, not vendor-governed)
- **Zombie**: Governed assets with no recent activity (abandoned subscriptions)
- **Governed**: Assets with IdP integration, CMDB registration, or vendor governance

#### 4. Findings (`src/aod/pipeline/findings/`)
Generates actionable findings for each asset:

| Finding | Description | Blocks AAM? |
|---------|-------------|-------------|
| `identity_gap` | No SSO integration | Yes |
| `finance_gap` | Spend without owner | Yes |
| `data_conflict` | Sources disagree | Yes |
| `cmdb_gap` | Not in asset registry | No |
| `governance_gap` | Missing governance controls | No |
| `duplication_risk` | Possible duplicate | No |

#### 5. Triage (`/api/triage/*`)
Provides workflow for reviewing and acting on discovered assets. Organizes findings into:
- **Red (Blocking)**: Must resolve before AAM connection
- **Yellow (Review)**: Cost optimization opportunities (zombies)
- **Green (Informational)**: Hygiene issues, non-blocking

#### 6. Policy Switchboard (`/switchboard`, `config/policy_master.json`)
Central configuration for all admission and classification logic:
- Activity windows (discovery, zombie detection)
- Finance thresholds (minimum spend for admission)
- Admission gates (require corroboration)
- Infrastructure domain handling (CDN, vendor portals)
- Custom exclusions (corporate root domains)

---

## Key Concepts

### Governance Trinity
An asset is **governed** if it has ANY of:
- **Visibility** (CMDB registration)
- **Validation** (IdP/SSO presence)
- **Control** (vendor-governed lifecycle)

### Alias Collapsing
Technical infrastructure domains collapse to their canonical vendor domain:
- `office365.com` → `microsoft.com`
- `microsoftonline.com` → `microsoft.com`

**Note:** Distinct products remain standalone (not collapsed):
- `zoom.us`, `zoomapp.io`, `zoom-meetings.net` → standalone (Zoom variants)
- `atlassian.net`, `trello.com`, `bitbucket.org` → standalone (Atlassian products)

### Authoritative vs Heuristic Matching
- **Authoritative methods** (domain, uri, canonical_name) can assert governance
- **Heuristic methods** (fuzzy, contains, vendor) are for enrichment only

---

## Known Policy Differences with Farm

The following discrepancies between AOD and Farm are **documented policy decisions**, not bugs:

### Category A: Infrastructure Variants (Collapse to Parent)
| Domain | AOD Behavior | Rationale |
|--------|--------------|-----------|
| `zoom.us` | → `zoom.com` | TLD variant, same service |
| `zoomapp.io` | → `zoom.com` | App infrastructure domain |
| `zoom-meetings.net` | → `zoom.com` | Meeting infrastructure |
| `adobelogin.com` | → `adobe.com` | Auth portal for Adobe |

**Farm Action Required:** Update expectations to accept parent domain as canonical key.

### Category B: Distinct Products (Standalone)
| Domain | AOD Behavior | Rationale |
|--------|--------------|-----------|
| `trello.com` | Standalone | Distinct product, separate attack surface |
| `bitbucket.org` | Standalone | Separate codebase and tech stack |

**Farm Action Required:** Update to expect these as separate assets from `atlassian.com`.

### Category C: Legacy Products (Collapse for Zombie Monitoring)
| Domain | AOD Behavior | Rationale |
|--------|--------------|-----------|
| `hipchat.com` | → `atlassian.com` | Discontinued product, zombie detection only |

**Farm Action Required:** Update expectations to accept parent domain.

---

## Reconciliation Status

**Current Accuracy:** ~99.3-99.5% combined (Shadow: 99.5-100%, Zombie: 97.5-99.2%)

Recent changes:
- **Jan 2026 (Phase D)**: Removed Zoom/Atlassian variants from alias collapsing. These domains are now STANDALONE per Farm contract:
  - `zoom.us`, `zoomapp.io`, `zoom-meetings.net`, `zoom-video.com` → standalone
  - `atlassian.net`, `trello.com`, `bitbucket.org` → standalone (distinct products)
- **Jan 2026 (Phase C)**: SSO-based IdP governance invariant. IdP records now provide governance ONLY if `has_sso=True`:
  - `has_sso=True` → IdP governance granted (zombies if inactive)
  - `has_sso=False` (even with `has_scim=True`) → NO IdP governance (shadows if no other governance)
  - SCIM is provisioning automation, not identity governance
- **Jan 2026 (Phase B)**: Removed overly permissive cross-TLD IdP matching. IdP governance now requires:
  1. Exact domain match, OR
  2. Same vendor via DOMAIN_TO_VENDOR mapping
  - Pure base-token matching (e.g., smartsuite.cloud vs smartsuite.org) no longer grants IdP governance

Remaining edge cases (~0.5-1% of total):
- `outlook.com`: Vendor-governed under Microsoft hierarchy
- `zoom-legacy.com`, `basecamp.com`: Legacy product alias handling

Note: After branch merges, Farm snapshots may regenerate, causing temporary misalignment with historical reports. Re-run from Farm to get fresh reconciliation.

### Debugging Discrepancies

1. Check `lens_match_debug` on assets to see HOW matches were made
2. Use `/api/debug/snapshot-drift-check?run_id=<run_id>` to detect snapshot regeneration
3. IdP governance requires `has_sso=True` - SCIM alone does not provide governance
4. IdP matching requires exact domain OR vendor mapping - no cross-TLD base-token matching

---

## Project Structure

```
src/
├── aod/
│   ├── api/routes/       # REST endpoints
│   │   ├── catalog.py    # Asset catalog endpoints
│   │   ├── farm.py       # Farm data fetching
│   │   ├── policy.py     # Policy switchboard API
│   │   ├── reconcile.py  # Reconciliation with Farm
│   │   ├── runs.py       # Pipeline run management
│   │   └── triage.py     # Triage workflow
│   ├── pipeline/         # Processing pipeline
│   │   ├── admission.py  # Admission gates
│   │   ├── classifications/  # Shadow/Zombie detection
│   │   ├── findings/     # Finding generators
│   │   └── vendor_governance.py
│   ├── db/               # Database models
│   ├── farm_client.py    # Farm API client
│   └── models/           # Pydantic models
├── main.py               # FastAPI application
config/
├── policy_master.json    # Policy configuration
static/
├── js/app.js            # Frontend application
├── css/main.css         # Styles
templates/
├── index.html           # Main UI template
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `FARM_URL_DEV` | Farm development URL |
| `FARM_URL_PROD` | Farm production URL (autonomos.farm) |
| `FARM_URL_MODE` | URL selection: `prod`, `dev`, `auto` |
| `REPLIT_DEPLOYMENT` | Auto-detected in production |

---

## Running Locally

The server runs on port 5000:
```bash
PYTHONPATH=/home/runner/workspace/src python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

---

## Farm Integration

Farm is the test data generator that creates realistic enterprise scenarios:
- 17,000+ asset permutations
- 37 edge case categories
- 800,000+ rule evaluations

Farm provides snapshots containing discovery observations, IdP records, CMDB entries, and finance transactions. AOD processes these through its pipeline and the reconciliation endpoint compares results.

**Note:** Farm uses autoscale and may take 10-15 seconds to wake from cold start. The UI shows a loading indicator during this time.

---

## UI Design

- **Palette:** Dark slate foundation with cyan and purple accents
- **Font:** Quicksand
- **Notifications:** Minimal, non-alarming feedback (cyan toast for loading states)

---

## Documentation

| File | Purpose |
|------|---------|
| `replit.md` | Project overview, architecture, current state |
| `docs/OPERATING_GUIDE.md` | Day-to-day operation of AOD + Farm |
| `docs/POLICY_SWITCHES.md` | Detailed policy configuration reference |
| `docs/guided-validation-tour-script.md` | Demo tour script |
| `docs/AOD_PRODUCT_SPEC.md` | Sales/prospect techno-functional spec |
