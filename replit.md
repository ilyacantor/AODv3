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
-   **Shadow Asset**: Active but lacks IdP or CMDB presence, WITH actionable spend (recurring finance or cloud evidence). One-time purchases and discovery-only signals are NOT flagged as shadow.
-   **Zombie Asset**: Has IdP/CMDB presence but no recent activity (90-day window).

**Actionable Spend Policy**: Shadow classification requires ACTIONABLE spend evidence:
- **Recurring finance** (contracts or recurring transactions with `HAS_RECURRING_FINANCE`), OR
- **Cloud evidence** (actual infrastructure with `HAS_CLOUD`)

Discovery alone (`HAS_DISCOVERY`) or one-time finance (`HAS_ONETIME_FINANCE`) without recurring spend/cloud is NOT sufficient for shadow classification. This filters expense reimbursements, one-time purchases, and discovery-only signals that don't represent ongoing SaaS subscriptions requiring governance action.

### Vendor Hypothesis (Inference Layer)

An inference layer generates a `vendor_hypothesis` (max 0.9 confidence) from domain patterns for discovery-only assets, based on curated domain-to-vendor mappings. This hypothesis is non-decisionable metadata and does not affect admission, classification, findings, or policy logic.

### API Structure

A FastAPI application exposes endpoints for triggering runs (`/api/runs/from-farm`), retrieving run details, assets, and findings, and debug/reconciliation endpoints.

### AOD Actual Results Emitter

AOD publishes its structured "actual" output (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) to Farm for reconciliation. AOD outputs canonical reason codes (e.g., `HAS_IDP`, `NO_CMDB`) for all assets, ensuring no blank reason codes.

### Domain-Keyed Asset Aggregation

Assets are aggregated using a domain-keyed approach. If evidence contains a registered domain, that domain becomes the `asset_key`. This ensures reconciliation accuracy by prioritizing domains from evidence, vendor lookups, and normalized names. `is_shadow`/`is_zombie` use OR semantics, and `reason_codes` are a union of all variants.

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