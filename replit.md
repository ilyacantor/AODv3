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
The UI features a single-page application using the AutonomOS color palette and Quicksand font. It provides a dropdown snapshot picker and drillable KPI cards. Finding categories are split into "Security Risks" (actionable, risk-bearing) and "Governance/Operational Findings" (hygiene, accuracy, readiness), with "Security Risks" as a standalone top-level KPI.

### Feature Specifications
*   **Finding Categories**: Findings are categorized into "Security Risks" (e.g., `identity_gap`, `finance_gap`) and "Governance/Operational Findings" (e.g., `cmdb_gap`, `duplication_risk`), sorted by category and severity.
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
*   **API Structure**: A FastAPI application exposes endpoints for triggering runs, retrieving details, and debug/reconciliation.
*   **Run Status Semantics**: Explicit run statuses (e.g., `UPSTREAM_ERROR`, `COMPLETED_WITH_RESULTS`).
*   **Database Design**: PostgreSQL persistence for `runs`, `assets`, `findings`, `artifacts`, and other related data.

## External Dependencies
*   **AOS Farm**: Upstream evidence source and recipient of reconciliation results.
*   **FastAPI**: Python web framework.
*   **Pydantic v2**: Data validation.
*   **asyncpg**: Asynchronous PostgreSQL driver.
*   **httpx**: Asynchronous HTTP client.
*   **PostgreSQL**: Primary database.