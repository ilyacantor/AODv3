# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence and generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets. This provides a clear, auditable view of an organization's digital footprint, supporting robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
### Core Design Principles
AOS Discover operates on principles of no ground truth ingestion, no ML/anomaly scores (relying on deterministic rules), determinism, and evidence-only decisions. It distinguishes between assets (systems) and artifacts (internal objects) to prevent inflated asset counts.

### Pipeline Architecture
The system employs a 7-stage sequential pipeline: validation, normalization, indexing, correlation, admission, artifact handling, and findings generation.

### UI/UX Decisions
The UI is a single-page application using the AutonomOS color palette and Quicksand font. It features a dropdown snapshot picker and drillable KPI cards for Lifecycle (Ingested, Validated, Rejected, Cataloged) and Classifications (Shadow, Zombie, Security Risks, Governance). KPI boxes include help icons with detailed explanations.

### Feature Specifications
*   **Finding Categories**: Security risks are categorized into Identity & Access, Shadow IT, and Data Integrity. Non-security findings are consolidated under Governance (e.g., CMDB gaps, duplication risks).
*   **Correlation Disambiguation**: Uses specific codes and fuzzy matching for evidence-driven resolution of multiple matches.
*   **Data Planes**: Evidence is sourced from Discovery, IdP, CMDB, Cloud, Endpoint, Network, and Finance.
*   **Derived Classifications**: `Shadow Asset` (discovered, active, ungoverned) and `Zombie Asset` (IdP/CMDB presence but no recent activity) are derived.
*   **Vendor Hypothesis**: An inference layer generates a `vendor_hypothesis` for discovery-only assets.
*   **Finance Admission Policy**: Requires recurring spend for finance evidence admission.
*   **AOD Results Emitter**: Publishes structured outputs (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) for reconciliation.
*   **Domain-Keyed Asset Aggregation**: Assets are aggregated using a domain-first approach, prioritizing registered domains (eTLD+1).
*   **Reconciliation Eligibility Modes**: Supports "Sprawl mode" (external services only) and "Infra mode" (all assets eligible).
*   **CMDB Correlation**: Utilizes multiple matching strategies including domain, canonical name, and fuzzy matching.
*   **Infrastructure Domain Exclusion**: Excludes internal infrastructure domains from shadow/zombie classification.
*   **LLM Fringe Resolution**: Provides classification assistance for ambiguous assets, persisting facts for reuse.
*   **Risk Case Aggregation**: Security findings include confidence, materiality, and triage_priority (P0, P1, P2).
*   **Tighter Trigger Gates**: Specific thresholds and activity evidence are required for `IDENTITY_GAP`, `FINANCE_GAP`, and `DATA_CONFLICT` findings.
*   **Policy Engine**: A configuration-driven engine for admission and classification, replacing hardcoded rules. It includes a schema, engine, and loader, with hot-reload support and API endpoints for configuration.
*   **API Structure**: A FastAPI application with modular routing for health, farm integration, runs, catalog, findings, triage, debug, and policy endpoints.
*   **Run Status Semantics**: Explicit run statuses (e.g., `UPSTREAM_ERROR`, `COMPLETED_WITH_RESULTS`).
*   **Database Design**: PostgreSQL persistence for all core data (`runs`, `assets`, `findings`, `artifacts`, `triage_actions`).
*   **Triage Persistence**: Triage actions (acknowledge, assign, defer, ignore) are saved to the database and restored.
*   **Traffic Light Provisioning**: A fail-closed asset provisioning system that controls flow to DCL with statuses: ACTIVE, REVIEW, QUARANTINE, BLOCKED, RETIRED, IGNORED.
*   **Smart Snapshot Selection**: Automatically selects the most recent snapshot on page load.
*   **Window Management**: Links between AOD and Farm reuse named windows.
*   **Overview Tab**: A React-based landing page providing a platform introduction, architecture overview, and call-to-action buttons.
*   **Guided Validation Run**: A narrated walkthrough of AOD discovery and verification with auto-navigation, factual overlays, and deterministic example selection.
*   **Reconciliation Fixes**: Key generation improvements, rejection of infrastructure domains, and stripping of environment suffixes.
*   **Data Architecture Fixes**: PSL-based domain extraction, comprehensive source-to-plane mapping, unknown source quarantine, domain-first identity, specific corroboration planes for discovery, TLD validation, and activity rollup for zombie classification.
*   **Iron Dome**: A unified early-stage validation gate applied at normalization to reject internal hostnames and normalize product names to canonical domains.
*   **Product Name Aliases**: Maps common product names to canonical domains.
*   **Triage Category Standardization**: Standardized Triage categories to Security Risks, Governance, Shadow IT, and Zombie IT for improved clarity.
*   **Aggressive Domain Merging**: Prevents "split brain" where name-only entities (e.g., "Airtable" from finance) and domain entities (e.g., "airtable.com" from discovery) create separate rows. Uses base token extraction and cross-referencing to ensure single unified record per tool.
*   **Gatekeeper Triage UI**: Workflow-oriented triage replacing tier-based system with three sections:
    - Blocked Assets (Shadow IT): `provisioning_status == QUARANTINE`, actions: Approve for AAM, Ban
    - Zombie Assets (Cleanup): `provisioning_status == REVIEW`, actions: Deprovision, Sanction
    - Governance Gaps: `provisioning_status == ACTIVE AND has_findings`, shows specific issues
*   **Asset Ownership Persistence**: Triage "Assign Owner" updates `asset.owner` directly, fixing the underlying data issue. The governance_gap finding short-circuits when asset.owner is set - no finding generated. On-conflict uses COALESCE to preserve existing owners.
*   **AAM Handoff API**: Architecture-correct endpoint at `/api/handoff/aam-manifest` provides Target Manifest for AAM (Adaptive API Mesh). AOD identifies assets, AAM executes connections, DCL receives streams. Payload includes `target_asset`, `provisioning_status`, `governance` (owner, auth_method), and `action_required`. Old `/catalog/dcl` endpoint deprecated.
*   **Status-Based Finding Suppression**: QUARANTINE, BLOCKED, IGNORED, and RETIRED assets do NOT generate secondary findings (Identity Gap, CMDB Gap, Governance Gap, etc.). Only ACTIVE and REVIEW assets are scanned for hygiene gaps. This prevents noise - users don't need 500 "Missing Owner" alerts for blocked malware.

## External Dependencies
*   **AOS Farm**: Upstream evidence source and reconciliation results recipient.
*   **FastAPI**: Python web framework.
*   **Pydantic v2**: Data validation.
*   **asyncpg**: Asynchronous PostgreSQL driver.
*   **httpx**: Asynchronous HTTP client.
*   **PostgreSQL**: Primary database.