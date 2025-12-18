# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS, an enterprise operating system. Its primary purpose is to ingest raw enterprise evidence and generate an Asset Catalog, a Run Log (audit trail), and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, focusing on accurately identifying and classifying enterprise assets based on observed evidence without relying on pre-adjudicated labels or machine learning. It aims to provide a clear and auditable view of an organization's digital footprint.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles

AOD Fresh adheres to principles of no ground truth ingestion, no ML/anomaly scores, determinism, evidence-only decisions, and a clear distinction between assets and artifacts.

### Pipeline Architecture

The system utilizes a 7-stage sequential pipeline: `validate_snapshot`, `normalize_observations`, `build_plane_indexes`, `correlate_entities`, `admission`, `artifact_handler`, and `findings_engine`.

### Finding Categories

Findings are categorized into "Security Risks" (actionable, risk-bearing) and "Governance/Operational Findings" (hygiene, accuracy, readiness), with defined severities and a specific sorting order. UI elements reflect this, featuring Security Risks and Findings as top-level KPIs.

### Correlation and Disambiguation

Correlation uses a five-pass process with evidence-driven disambiguation codes (`MULTI_ENV`, `LEGACY`, `DUPLICATE`, `PARENT_VENDOR`, `UNRESOLVED`) and fuzzy matching with Levenshtein distance for typos. A `KNOWN_DISTINCT_PRODUCTS` blocklist prevents false positives.

### Data Planes

Evidence is sourced from 7 distinct planes: Discovery, IdP, CMDB, Cloud, Endpoint, Network, and Finance.

### Derived Classifications

**Shadow Asset** and **Zombie Asset** classifications are derived post-pipeline based on discovery presence, activity recency (90-day window), and governance status. Finance evidence acts as context but does not influence shadow classification directly.

### Vendor Hypothesis

An inference layer provides a `vendor_hypothesis` (max 0.9 confidence) for discovery-only assets, based on curated domain-to-vendor mappings. This is non-decisionable metadata.

### API Structure

A FastAPI application exposes endpoints for triggering runs, retrieving run details, assets, and findings, and debug/reconciliation.

### Finance Admission Policy

Finance evidence requires recurring spend (`is_recurring=true` and `amount > 0`) to qualify for admission, excluding one-time purchases.

### AOD Actual Results Emitter

AOD publishes structured outputs (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) to Farm, providing canonical reason codes for all assets.

### Domain-Keyed Asset Aggregation and Normalization

Assets are aggregated using a domain-keyed approach, prioritizing domains from evidence. A centralized `domain_normalization.py` module, leveraging the Public Suffix List, handles canonical domain extraction (eTLD+1) for keying and reconciliation.

### Finance Domain-First Linking

Finance correlation prioritizes domain matching, followed by canonical name match, and then vendor-product match as a fallback. Reason codes differentiate linking confidence (`HAS_FINANCE_DOMAIN_LINKED`, `HAS_FINANCE_VENDOR_ONLY`, `HAS_FINANCE`).

### Activity Recency Determinism

Activity recency is computed deterministically, prioritizing timestamps from IdP, Discovery, Cloud, and Finance to determine `latest_activity_at` for `RECENT_ACTIVITY` (within 90 days) or `STALE_ACTIVITY`. Zombie status reasons include the timestamp source (e.g., "from idp_last_login", "from discovery_observed") for full traceability. Debug logs emit `ZOMBIE_DIAGNOSTIC` entries for each classification.

### Reconciliation Eligibility Modes

The system supports "Sprawl mode" (default, external services only) and "Infra mode" (all assets, including internal identifiers) for reconciliation eligibility.

### CMDB Correlation

CMDB correlation uses multiple strategies: domain matching, canonical name matching with vendor validation, fuzzy matching (relative threshold `distance/max_len ≤ 0.20`), contains matching, name contains domain token (≥6 chars), and vendor-based matching (vendor, domain-to-vendor, vendor fallback). Governance reason codes (`HAS_CMDB`, `HAS_IDP`) are based on lens_status.

### Infrastructure Domain Exclusion

A blocklist of `INFRASTRUCTURE_DOMAINS` prevents internal infrastructure components from being flagged as shadow/zombie.

### LLM Fringe Resolution

An LLM-based fringe resolver (Gemini-first, OpenAI fallback, 0.80 confidence) assists with ambiguous assets (unknown asset_type, governance gap, ambiguous vendor). LLM facts are persisted, and high-confidence INFRA_TECH classifications are excluded from shadow/zombie. LLM-adjudicated matches can promote assets to governed status.

### Explain Non-Flag Endpoint

A dedicated endpoint `/api/reconcile/explain-nonflag` provides detailed reasons why assets are not flagged as shadow/zombie.

### Run Status Semantics

Runs return explicit statuses: `UPSTREAM_ERROR`, `INVALID_SNAPSHOT`, `INVALID_INPUT_CONTRACT`, `COMPLETED_NO_ASSETS`, `COMPLETED_WITH_RESULTS`.

### Database Design

PostgreSQL is used for persistence, storing `runs`, `assets`, `findings`, `artifacts`, `observation_samples`, `ambiguous_matches`, and `rejections`.

### Frontend

A single-page application built with AutonomOS color palette and Quicksand font, offering snapshot selection and drillable KPI cards.

## External Dependencies

-   **AOS Farm**: Upstream evidence source via HTTP and recipient of reconciliation results.
-   **FastAPI**: Python web framework for API.
-   **Pydantic v2**: Data validation and serialization.
-   **asyncpg**: Asynchronous PostgreSQL driver.
-   **httpx**: Asynchronous HTTP client.
-   **PostgreSQL**: Primary database.