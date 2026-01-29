# AOD - Asset Observation & Discovery

## What AOD Does

AOD is the **discovery engine** for the autonomOS platform. Before an organization can connect, unify, or automate anything, it must first know what exists. AOD answers the fundamental question: *"What software assets does this organization actually use?"*

### The Problem AOD Solves

Enterprises typically have 1,000+ applications, but IT only knows about a fraction of them. The rest are:
- **Shadow IT**: Apps employees adopted without IT approval (Notion, Airtable, personal Dropbox)
- **Zombie Assets**: Licensed software nobody uses anymore but still costs money
- **Ungoverned Systems**: Critical tools operating outside security and compliance controls

AOD discovers ALL of these by ingesting signals from multiple sources and correlating them into a single source of truth.

### Core Functional Capabilities

1. **Multi-Source Discovery**
   - Ingests data from identity providers (Okta, Azure AD), expense systems, browser telemetry, network logs, CMDBs, and cloud inventories
   - Correlates signals to identify unique applications even when named differently across sources
   - Handles alias collapsing (e.g., `office365.com`, `outlook.com`, `microsoft365.com` → `microsoft.com`)

2. **Governance Classification**
   - **Governed**: Assets with visibility (in CMDB), validation (SSO-enabled), or control (vendor-managed lifecycle)
   - **Shadow IT**: Assets in use but missing from official inventories — security and compliance blind spots
   - **Zombie**: Assets in CMDB/licensed but with no recent activity — cost optimization opportunities

3. **Finding Generation**
   - Surfaces actionable issues for each asset:
     - **Identity Gap** (Red): Users accessing app without SSO — security risk
     - **Finance Gap** (Yellow): No expense records for paid service — potential rogue spending
     - **Data Conflict** (Yellow): Multiple sources disagree on ownership or status
     - **Stale Activity** (Yellow): No usage in 90+ days — zombie candidate
   - Findings have severity levels: Red (blocking), Yellow (review), Green (informational)

4. **Triage Workflow**
   - Organizes discovered issues into workqueues: Firewall (security), Risk (compliance), Hygiene (cleanup)
   - Enables teams to take action: Sanction (approve shadow IT), Ban (block access), Deprovision (retire zombie)
   - Tracks disposition state and ownership for audit trails

5. **System of Record (SOR) Detection**
   - Identifies which applications are authoritative data sources for specific domains (HR, Finance, CRM)
   - Uses signal-based scoring: CMDB flags, known SOR vendors, middleware presence, SCIM enablement
   - Outputs confidence bands (high/medium/low) so downstream systems know which data to trust

6. **Fabric Plane Detection**
   - Recognizes integration "motherships" (MuleSoft, Workato, Snowflake, Kafka, Kong)
   - Rather than connecting to 500 individual apps, identifies the 3-4 fabric planes that aggregate them
   - Tags assets with `connected_via_plane` routing so AAM connects efficiently

7. **AAM Handoff**
   - Exports ConnectionCandidates to AAM (Adaptive API Mesh) for connection
   - Includes execution signals: `execution_allowed` and `action_type`
   - Blocking findings → `inventory_only` (human review required)
   - Clear/overridden → `provision` (safe for auto-connection)
   - AAM receives complete inventory but respects execution gates

## User Interface

### Console Tab
- Fetch discovery snapshots from Farm (test data generator) or production sources
- Execute DiscoveryScans and view run history
- Monitor scan timing and status

### Triage Tab
- **Firewall Section**: Shadow IT and security-critical items requiring immediate attention
- **Risk Section**: Compliance and governance gaps needing review
- **Hygiene Section**: Zombie assets and cleanup opportunities
- Actions: Sanction, Ban, Deprovision, Assign, Defer, Ignore

### Catalog View
- Browse all discovered assets with full detail
- Filter by classification, governance status, or findings
- View evidence sources and confidence scores
- See triage disposition badges

### Policy Tab
- Configure governance rules and thresholds
- Define activity windows for zombie detection
- Set finance thresholds and custom exclusions
- View policy manifest exported to AAM

### Handoff Tab
- Review ConnectionCandidates ready for AAM
- See execution signals and blocking reasons
- Monitor handoff history across runs

### Overview Tab
- Platform introduction and educational content
- Interactive pipeline visualization
- Guided tour of AOD capabilities

## User Preferences

- Simple language with detailed explanations for new concepts
- Iterative development with clear communication at each step
- Ask before major architectural changes or new dependencies
- Do not modify the `docs/` folder

## Technical Architecture

### DiscoveryScan Pipeline

AOD processes raw observations through a 7-stage sequential pipeline:

1. **Validation**: Verify input data integrity and format
2. **Normalization**: Standardize domains, names, and identifiers
3. **Indexing**: Build searchable asset registry
4. **Correlation**: Match signals to unique assets across sources
5. **Admission**: Apply governance rules and generate findings
6. **Artifact Handling**: Process SOR scoring, fabric plane detection
7. **Output**: Produce catalog and ConnectionCandidates

Each scan execution is tracked by `scan_session_id` for lineage.

### Key Concepts

- **Governance Trinity**: An asset is governed if it has Visibility (CMDB), Validation (IdP/SSO), or Control (vendor lifecycle)
- **Policy Switchboard**: Central configuration (`config/policy_master.json`) governing all classification logic
- **Enterprise Presets**: Inferred integration patterns (iPaaS-centric, Warehouse-centric, etc.) that determine AAM connection strategy

### Project Structure

```
src/
├── aod/
│   ├── api/routes/       # FastAPI endpoints (catalog, triage, handoff, policy)
│   ├── pipeline/         # DiscoveryScan stages and orchestration
│   ├── models/           # Data models and output contracts
│   ├── core/policy/      # Policy schema and manifest builder
│   └── db/               # Database operations and migrations
static/
├── css/                  # Stylesheets
├── js/                   # Frontend application logic
└── overview/             # React-based overview module
templates/
└── index.html            # Main application template
config/
└── policy_master.json    # Central policy configuration
```

### Key Files

| File | Purpose |
|------|---------|
| `src/aod/pipeline/pipeline_executor.py` | Main DiscoveryScan orchestrator |
| `src/aod/pipeline/sor_scoring.py` | System of Record signal scoring |
| `src/aod/api/routes/catalog.py` | Asset catalog API and provisioning |
| `src/aod/api/routes/triage.py` | Triage action management |
| `src/aod/api/routes/handoff.py` | AAM ConnectionCandidate export |
| `src/aod/core/policy/manifest.py` | Policy manifest builder for AAM |
| `static/js/app.js` | Frontend application logic |

### External Dependencies

- **Farm**: Test data generator for discovery snapshots (identity, finance, CMDB, cloud)
- **AAM**: Receives ConnectionCandidates for connection orchestration
- **DCL**: Data Connectivity Layer for unified data ingestion (via AAM, not direct)
- **PostgreSQL**: Primary database for assets, runs, and triage state

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/catalog/runs/{run_id}` | GET | Fetch assets for a discovery run |
| `/api/catalog/assets/{id}/provisioning` | POST | Apply triage action to asset |
| `/api/triage/data/{run_id}` | GET | Get triage workqueue for run |
| `/api/triage/action` | POST | Record triage decision |
| `/api/handoff/aam/candidates` | POST | Export ConnectionCandidates to AAM |
| `/api/policy/manifest` | GET | Export governance rules for AAM |
| `/api/runs/{run_id}/derived` | GET | Get derived classifications (shadow, zombie lists) |

## Design System

- **Colors**: Dark slate foundation (#0f172a), cyan accent (#0bcad9), purple secondary (#a855f7)
- **Typography**: Quicksand font family
- **Notifications**: Minimal cyan toast messages
- **Components**: Reusable overview template available in `handoff/aos-overview-template/`

## Recent Changes

- **2026-01-29**: Farm authoritative data fix - Handoff candidates now use Farm's fabric_planes and sors data, not computed values
- **2026-01-29**: Handoff tab displays Farm's fabric planes and SORs in dedicated sections with source badges
- **2026-01-28**: Header branding updated - Logo replaced with text "AOD Asset Observation & Discovery"
- **2026-01-28**: Triage item_type fix - Frontend now passes classification to backend for deterministic lookup
- **2026-01-28**: Overview template packaged for reuse across AOS modules
- **2026-01-23**: Execution signaling - ConnectionCandidates include `execution_allowed` and `action_type` fields
- **2026-01-23**: PolicyManifestBuilder - Exports governance rules for AAM consumption
- **2026-01-22**: AAM handoff architecture - ConnectionCandidate output contract implemented
- **2026-01-21**: SOR scoring engine - Signal-based identification with confidence bands
- **2026-01-20**: Fabric Plane detection - Identifies integration motherships for efficient connection
