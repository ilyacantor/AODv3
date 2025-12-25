# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover (formerly AOD Fresh) is the discovery module of AutonomOS, an enterprise operating system. Its core purpose is to ingest raw enterprise evidence to produce an Asset Catalog, a Run Log, and Explainable Findings. The system is deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets based on observed evidence. This contributes to a clear and auditable view of an organization's digital footprint, supporting business vision for robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
### Core Design Principles
AOD Fresh operates on principles of no ground truth ingestion (rejecting banned fields), no ML/anomaly scores (relying on deterministic rules and explainable correlation), determinism (identical outputs for identical inputs), and evidence-only decisions. It explicitly distinguishes between assets (systems) and artifacts (internal objects) to prevent inflated asset counts.

### Pipeline Architecture
The system utilizes a 7-stage sequential pipeline:
1.  `validate_snapshot.py`: Schema validation.
2.  `normalize_observations.py`: Data normalization and entity derivation.
3.  `build_plane_indexes.py`: Index creation for correlation.
4.  `correlate_entities.py`: Five-pass correlation with disambiguation.
5.  `admission.py`: Asset admission criteria.
6.  `artifact_handler.py`: Artifact identification.
7.  `findings_engine.py`: Deterministic findings generation.

### UI/UX Decisions
The UI features a single-page application using the AutonomOS color palette and Quicksand font. Frontend assets are organized as:
- `templates/index.html`: HTML structure with modals (~420 lines)
- `static/css/main.css`: Extracted CSS styles (~395 lines)
- `static/js/app.js`: Extracted JavaScript (~2,270 lines)
- Static assets use cache-busting version params (?v=N)

It provides a dropdown snapshot picker and drillable KPI cards organized into two rows:
*   **Lifecycle Row**: Ingested (observations) → Validated (passed processing) → Rejected → Cataloged (assets)
*   **Classifications Row**: Shadow, Zombie, Security Risks, Governance

Each KPI box includes a help icon (?) in the top right corner with detailed tooltip explanation. Finding categories are split into "Security Risks" (actionable, risk-bearing) and "Governance" (hygiene, accuracy, readiness including CMDB gaps).

### Feature Specifications
*   **Finding Categories (Dec 2025 Taxonomy)**: Security risks are categorized into three buckets:
    - **Identity & Access** (`identity_access`): IDENTITY_GAP - ungoverned access paths
    - **Shadow IT** (`shadow_it`): FINANCE_GAP - financially-backed shadow systems  
    - **Data Integrity** (`data_integrity`): DATA_CONFLICT - conflicting authoritative data
    
    Non-security findings are consolidated into Governance:
    - **Governance** (includes `visibility_gap`, `governance_hygiene`): CMDB_GAP (partial governance), GOVERNANCE_GAP, DUPLICATION_RISK - exposure amplifiers that reduce control plane accuracy
*   **Correlation Disambiguation**: Employs specific codes (e.g., `MULTI_ENV`, `DUPLICATE`) and fuzzy matching (Levenshtein distance) to resolve multiple matches, always evidence-driven.
*   **Data Planes**: Evidence is sourced from Discovery, IdP, CMDB, Cloud, Endpoint, Network, and Finance planes.
*   **Derived Classifications**: `Shadow Asset` (discovered, active, ungoverned) and `Zombie Asset` (IdP/CMDB presence but no recent activity) are derived post-pipeline. Shadow classification specifically excludes finance evidence as a trigger.
*   **Vendor Hypothesis**: An inference layer generates a `vendor_hypothesis` for discovery-only assets based on domain patterns, used as non-decisionable metadata.
*   **Finance Admission Policy**: Requires recurring spend for finance evidence to qualify for admission.
*   **AOD Results Emitter**: Publishes structured "actual" outputs (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) to Farm for reconciliation with canonical reason codes.
*   **Domain-Keyed Asset Aggregation**: Assets are aggregated using a domain-first approach, prioritizing registered domains (eTLD+1) for asset keys. Domain evidence takes precedence over vendor inference.
*   **Reconciliation Eligibility Modes**: Supports "Sprawl mode" (default, external services only) and "Infra mode" (all assets eligible) for shadow/zombie classification.
*   **CMDB Correlation**: Utilizes multiple matching strategies including domain, canonical name, fuzzy, contains, domain token, and vendor matching, with vendor validation for accuracy.
*   **Infrastructure Domain Exclusion**: Excludes internal infrastructure domains from shadow/zombie classification.
*   **LLM Fringe Resolution**: For ambiguous assets, an LLM-based resolver provides classification assistance, persisting facts for reuse and excluding INFRA_TECH assets.
*   **Risk Case Aggregation**: Security findings include confidence, materiality, and triage_priority fields. P0 = HIGH confidence + HIGH materiality; P1 = HIGH+MED or MED+HIGH; P2 = everything else. UI shows actionable (P0+P1) as headline.
*   **Tighter Trigger Gates**: IDENTITY_GAP requires strong activity evidence (cloud/finance/multi-plane); FINANCE_GAP requires recurring spend ≥$200/mo; DATA_CONFLICT only fires for security-relevant fields (owner, environment, data_classification, etc.) with deduplication by (asset, field).
*   **Policy Engine (Dec 2025)**: Configuration-driven admission and classification replacing hardcoded rules:
    - `src/aod/core/policy/schema.py`: PolicyConfig dataclasses (AdmissionConfig, ScopeConfig)
    - `src/aod/core/policy/engine.py`: Pure-function PolicyEngine (no DB dependencies)
    - `src/aod/core/policy/loader.py`: Config loading with hot-reload support
    - `config/policy.json`: Default configuration (minimum_spend=200, noise_floor=2, zombie_window_days=90)
    - API: `GET /api/v1/policy/config` exposes config for Farm alignment
    - API: `POST /api/v1/policy/reload` hot-reloads config from disk
    - Parallel validation: Pipeline runs both legacy and PolicyEngine, logs mismatches
    - Seed lists: corporate_root_domains (empty - SaaS vendors are legitimate targets), infrastructure_domains (46) exposed via API
    - **Critical Fix (Dec 2025)**: CORPORATE_ROOT_DOMAINS was incorrectly populated with 27 major SaaS vendors (pagerduty.com, okta.com, zendesk.com, etc.) causing them to be killed at admission. Fixed by emptying the list - SaaS platforms are legitimate discovery targets, not corporate marketing websites. Corporate root domains are meant for tenant's OWN marketing domains only.
    - Controlled cutover: `scope.use_policy_engine` flag (default: false) enables PolicyEngine as primary
    - Conservative mode: When enabled, PolicyEngine can only reduce admissions (block what legacy allows)
    - Farm integration complete: Farm fetches policy from AOD with 5-min cache, uses seed lists from API
*   **API Structure**: A FastAPI application with modular routing architecture:
    - `src/aod/api/routes/health.py`: Health check endpoint
    - `src/aod/api/routes/farm.py`: Farm integration endpoints (tenants, snapshots)
    - `src/aod/api/routes/runs.py`: Run management endpoints (create, list, details)
    - `src/aod/api/routes/catalog.py`: Asset catalog endpoints
    - `src/aod/api/routes/findings.py`: Findings and artifacts endpoints
    - `src/aod/api/routes/triage.py`: Triage action persistence endpoints
    - `src/aod/api/routes/debug.py`: Debug and reconciliation endpoints
    - `src/aod/api/routes/policy.py`: Policy configuration endpoints
    - `src/aod/api/schemas.py`: Shared Pydantic request/response models
    - `src/aod/api/deps.py`: Shared dependencies and helpers
*   **Run Status Semantics**: Explicit run statuses (e.g., `UPSTREAM_ERROR`, `COMPLETED_WITH_RESULTS`).
*   **Database Design**: PostgreSQL persistence for `runs`, `assets`, `findings`, `artifacts`, `triage_actions`, and other related data.
*   **Triage Persistence**: Triage actions (acknowledge, assign, defer, ignore) are saved to the database and restored when viewing the Triage tab. Status badges show current state with visual distinction for triaged items.
*   **Smart Snapshot Selection**: On page load, the tenant with the most recent snapshot is automatically selected, marked with ★ (Latest).
*   **Window Management**: Links between AOD and Farm reuse named windows (`aos_discover`, `aos_farm`) instead of opening new tabs.
*   **Overview Tab**: React-based landing page built with Vite, Tailwind CSS, and framer-motion. Source in `client/`, builds to `static/overview/`. Displays AutonomOS platform introduction, AOD gateway explanation, interactive architecture iframe from overview.autonomos.software, and call-to-action buttons for Guided Validation.
*   **Guided Validation Run**: Narrated walkthrough of AOD discovery and verification. Phases: Entry framing (0), Discovery run (3), Shadows inspection (4), Triage demonstration (5), Catalog review (6), Free exploration (8). Features auto-navigation, factual overlays, Farm handoff via URL params, and deterministic example selection with fallback handling. Tour state persisted in localStorage (`aod_guided_tour`). Implemented in `static/js/tour.js`.
*   **Reconciliation Fixes (Dec 2025)**: Key generation uses VENDOR_TO_DOMAIN before falling back to name normalization; infrastructure domains (redis.com, mongodb.com, postgresql.org, etc.) rejected at admission GATE 2; environment suffixes (-prod, -dev, -staging, -legacy) stripped during canonical name derivation.
*   **Data Architecture Fixes (Dec 2025)**: 
    - **PSL-based Domain Extraction**: Uses tldextract library for proper eTLD+1 handling (e.g., observability.prod.elasticcloud.app → elasticcloud.app)
    - **Comprehensive Source-to-Plane Mapping**: 60+ known sources mapped to 7 planes (network, endpoint, idp, cloud, finance, cmdb, discovery)
    - **Unknown Source Quarantine**: Unknown sources return None and are excluded from plane diversity counts to prevent signal inflation
    - **Domain-First Identity**: Entities without resolvable domains are rejected and persisted to rejections table
    - **Discovery Corroboration Planes**: Only network, endpoint, idp, cloud, discovery count toward discovery admission; finance and CMDB excluded from discovery corroboration
    - **TLD Validation (GATE 0)**: Entities without valid public TLD suffixes (internal hostnames) rejected at admission start
    - **Activity Rollup for Zombie Classification**: Subdomain activity propagates to parent domains (e.g., mail.google.com activity counts toward google.com), preventing false zombie classifications
*   **Iron Dome (Dec 2025)**: Unified early-stage validation gate applied at normalization (Stage 2) before entity creation:
    - `validate_key_integrity(key)`: Uses tldextract to reject internal hostnames (no valid TLD suffix like `images694`, `auth-service`, `token865`)
    - `normalize_name_to_domain(name)`: Resolves product names to canonical domains BEFORE validation (Okta → okta.com, Workday → workday.com)
    - All Discovery observations pass through Iron Dome before becoming CandidateEntities
    - CMDB/IdP/Finance/Cloud records are ONLY used for correlation, NOT entity creation - Iron Dome at normalization is sufficient
    - Rejected observations persisted to rejections table with `iron_dome` rejection type
    - GATE 0 in admission.py retained as final safety net
*   **Product Name Aliases**: Maps common product names to canonical domains (Microsoft 365 → microsoft.com, Google Workspace → google.com, AWS → amazonaws.com, Office 365 → microsoft.com).

## External Dependencies
*   **AOS Farm**: Upstream evidence source and recipient of reconciliation results.
*   **FastAPI**: Python web framework.
*   **Pydantic v2**: Data validation.
*   **asyncpg**: Asynchronous PostgreSQL driver.
*   **httpx**: Asynchronous HTTP client.
*   **PostgreSQL**: Primary database.