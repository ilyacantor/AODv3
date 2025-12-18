# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS, an enterprise operating system. It ingests raw enterprise evidence and produces an Asset Catalog (systems only), a Run Log (audit trail), and Explainable Findings (rule-based, no ML/anomaly scores). The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels. Its core purpose is to accurately identify and classify enterprise assets based on observed evidence, contributing to a clear and auditable view of an organization's digital footprint.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles

- **No Ground Truth Ingestion**: Rejects banned fields (e.g., `is_shadow_it`) to ensure evidence-only processing.
- **No ML/Anomaly Scores**: Relies solely on deterministic rules and explainable correlation.
- **Deterministic**: Guarantees identical outputs for identical inputs with stable ordering.
- **Evidence-Only Decisions**: All admissions and findings are derived exclusively from raw evidence.
- **Assets vs. Artifacts**: Distinguishes systems (assets) from internal objects (artifacts) to prevent inflated asset counts.

### Pipeline Architecture

AOD Fresh uses a 7-stage sequential pipeline:
1.  `validate_snapshot.py`: Schema validation and banned field rejection.
2.  `normalize_observations.py`: Normalizes data and derives candidate entities.
3.  `build_plane_indexes.py`: Creates indexes for efficient correlation.
4.  `correlate_entities.py`: Performs five-pass correlation with disambiguation.
5.  `admission.py`: Applies criteria to determine assets.
6.  `artifact_handler.py`: Identifies and records artifacts.
7.  `findings_engine.py`: Generates deterministic findings.

### Correlation Disambiguation

The system uses specific codes (e.g., `MULTI_ENV`, `LEGACY`, `DUPLICATE`, `PARENT_VENDOR`, `UNRESOLVED`) to resolve multiple matches. Disambiguation is evidence-driven, requiring CMDB fields to support resolution; otherwise, matches remain `AMBIGUOUS`. Prevention mechanisms include `PARENT_VENDOR` to avoid incorrect vendor matching and `KNOWN_DISTINCT_PRODUCTS` blocklist for substring false positives (e.g., "box" vs. "dropbox"). Fuzzy matching handles typos with Levenshtein distance for names ≥4 characters.

### Data Planes

Evidence is sourced from 7 planes: Discovery, IdP, CMDB, Cloud, Endpoint, Network, and Finance.

### Derived Classifications

Shadow and Zombie classifications are derived post-pipeline:
-   **Shadow Asset**: Discovered + Active + Ungoverned (has discovery/cloud evidence, recent activity within 90 days, but NO IdP or CMDB presence).
-   **Zombie Asset**: Has IdP/CMDB presence but no recent activity (90-day window).

**Shadow Policy (Dec 2025):** Finance is NOT a trigger or gate for shadow classification. Shadow depends ONLY on discovery presence + activity recency + governance status. Finance evidence is retained as context/annotation only (reason codes like `HAS_FINANCE`/`NO_FINANCE` for priority/scoring), but never affects the shadow True/False decision.

### Vendor Hypothesis (Inference Layer)

An inference layer generates a `vendor_hypothesis` (max 0.9 confidence) from domain patterns for discovery-only assets, based on curated domain-to-vendor mappings. This hypothesis is non-decisionable metadata and does not affect admission, classification, findings, or policy logic.

### API Structure

A FastAPI application exposes endpoints for triggering runs (`/api/runs/from-farm`), retrieving run details, assets, and findings, and debug/reconciliation endpoints.

### Finance Admission Policy

Finance evidence requires **recurring spend** to qualify for admission:
- Contracts must have `is_recurring=true` and `amount > 0`
- Transactions must have `is_recurring=true` and `amount > 0`

One-time purchases and expense reimbursements are not actionable shadow IT and are excluded from finance-based admission.

### AOD Actual Results Emitter

AOD publishes its structured "actual" output (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) to Farm for reconciliation. AOD outputs canonical reason codes (e.g., `HAS_IDP`, `NO_CMDB`) for all assets, ensuring no blank reason codes.

### Domain-Keyed Asset Aggregation

Assets are aggregated using a domain-keyed approach. If evidence contains a registered domain, that domain becomes the `asset_key`. This ensures reconciliation accuracy by prioritizing domains from evidence, vendor lookups, and normalized names. `is_shadow`/`is_zombie` use OR semantics, and `reason_codes` are a union of all variants (with contradictory codes deduplicated - HAS_* takes precedence over NO_*).

**Entity Domain Upgrade (Dec 2025):** During normalization, if an entity is first created from non-domain evidence (e.g., "Miro" from IdP) and later receives domain evidence (e.g., "miro.com" from discovery), the entity is upgraded to include the domain. The entity is re-keyed under the domain-based key, and all observations are merged. This ensures assets like miro.com and loom.com use domain-based keys even when initial evidence lacks domains.

### Reconciliation Eligibility Modes

Reconciliation eligibility is mode-based:
- **Sprawl mode** (default): Only external services (domains, known SaaS) are eligible for shadow/zombie classification. Internal identifiers (elasticsearchlogs, postgresmain) are excluded to prevent false positives.
- **Infra mode**: All assets are eligible, including internal identifiers. Use for infrastructure discovery reconciliation.

Mode can be specified via the `/runs/resync` endpoint: `{"run_id": "...", "mode": "infra"}`. Initial run creation uses sprawl mode by default.

### CMDB Correlation

CMDB correlation uses multiple matching strategies:
1. **Canonical name matching** - Exact normalized name match with vendor validation
2. **Fuzzy matching** - Levenshtein distance for typos with KNOWN_DISTINCT_FUZZY blocklist
3. **Contains matching** - Substring matching with KNOWN_DISTINCT_PRODUCTS blocklist
4. **Vendor matching** - Entity vendor → CMDB vendor product index
5. **Domain-to-vendor matching** - Entity domain → DOMAIN_TO_VENDOR → CMDB vendor (e.g., trello.com → Atlassian → Trello CMDB record)

**Fuzzy Matching Blocklist (Dec 2025):** KNOWN_DISTINCT_FUZZY prevents false positive fuzzy matches between distinct products with similar names (e.g., miro↔jira distance=2, loom↔zoom distance=1). These pairs are blocklisted from fuzzy matching to prevent incorrect CMDB correlations.

**Vendor Validation (Dec 2025):** Canonical name matches against CMDB are validated using entity domain → DOMAIN_TO_VENDOR or entity name → VENDOR_TO_DOMAIN lookups to ensure the matched CMDB record's vendor matches the expected vendor for the entity.

Domain matching is not directly available for CMDB as the data model doesn't include domain fields, but the domain-to-vendor lookup bridges this gap.

### Explain Non-Flag Endpoint

A `POST /api/reconcile/explain-nonflag` endpoint allows Farm to query why specific assets are NOT flagged as shadow/zombie, providing detailed reasons and decisions.

### Run Status Semantics

Runs return explicit statuses: `UPSTREAM_ERROR`, `INVALID_SNAPSHOT`, `INVALID_INPUT_CONTRACT`, `COMPLETED_NO_ASSETS`, `COMPLETED_WITH_RESULTS`.

### Database Design

PostgreSQL is used for persistence, configured via `SUPABASE_DB_URL` or `DATABASE_URL`. It includes tables for `runs`, `assets`, `findings`, `artifacts`, `observation_samples`, `ambiguous_matches`, and `rejections`. IDs are deterministic and run-scoped.

### Frontend

A single-page application using AutonomOS color palette and Quicksand font, providing a dropdown snapshot picker and drillable KPI cards.

## External Dependencies

-   **AOS Farm**: Upstream evidence source, providing snapshots via HTTP (`FARM_URL`) and receiving reconciliation results. AOD uses `farm_adapter.py` to normalize Farm's schema.
-   **FastAPI**: Python web framework for API development.
-   **Pydantic v2**: Data validation and serialization.
-   **asyncpg**: Asynchronous PostgreSQL database driver.
-   **httpx**: Asynchronous HTTP client for Farm communication.
-   **PostgreSQL**: Primary database for persistence.