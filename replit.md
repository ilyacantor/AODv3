# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence to generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets. This provides a clear, auditable view of an organization's digital footprint, supporting robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
AOS Discover follows a strict architectural design based on several core principles: no ground truth ingestion, no ML/anomaly scores, determinism, and evidence-only decisions. It distinguishes between assets and artifacts to prevent asset count inflation.

The system uses a 7-stage sequential pipeline for processing: Validation, Normalization, Indexing, Correlation, Admission, Artifact Handling, and Findings Generation.

**Governance Trinity:** An asset is classified as "Shadow" if it fails any of the following:
-   **Visibility**: Registered in CMDB
-   **Validation**: Present in IdP (sanctioned/SSO)
-   **Control**: Managed lifecycle tied to owner
Finance presence does not equate to governance; there is no "Grey IT".

**Derived Classifications:**
-   **Activity Status**: RECENT (active within 90 days), STALE (inactive beyond 90 days), or NONE.
-   **Anchored Predicate**: An asset is "anchored" if it has an IdP, CMDB, finance, or cloud resource match.
-   **Shadow Asset**: Ungoverned (NOT has_idp AND NOT has_cmdb) AND RECENT activity.
-   **Financial Anchor Governance Gap**: Shadow asset with ongoing finance.
-   **Zombie Asset**: Governed (has_idp OR has_cmdb) AND STALE activity AND ongoing_finance.
-   **Parked Asset**: Ungoverned (NOT has_idp AND NOT has_cmdb) AND STALE activity.

**Governance Policy:** `is_governed = has_idp OR has_cmdb`. This policy applies consistently across all logic.

**Key Technical Implementations & Features:**
-   **Admission Gates:** Finance alone is not sufficient for admission; it requires corroboration with governance or sufficient discovery.
-   **Domain Normalization:** Standardizes domain names by stripping subdomains to eTLD+1 and collapsing alias domains.
-   **Tenant Token Indexing:** Extracts and indexes tenant tokens from subdomain patterns for cross-matching.
-   **Correlation Consistency:** Ensures consistent domain normalization across all correlation phases.
-   **Activity Status & Zombie Detection:** Accurate calculation of activity status based on observation and plane timestamps, crucial for identifying zombie assets. Fail-safe to "CLEAN" if no activity timestamps are available.
-   **Domain Recovery:** Recovers entity domains from correlated plane records (IdP, CMDB, Cloud, Finance) when discovery observations lack domain fields.
-   **Indexing Enhancements:** Extracts and indexes base names from registered domains and vendor names from finance transactions to improve correlation.
-   **Token-Based Finance Correlation:** Uses token-based matching for finance transactions. Requirements: (1) domain base token ≥4 chars, (2) NOT in GENERIC_TOKENS blocklist (cloud, data, online, digital, software, service, etc.), (3) domain base must match the FIRST token of vendor name (primary brand). VENDOR_PREFIXES skipped: the, a, an, team, inc, corp, llc, ltd, co, by. Hyphen normalization collapses "service-now" → "servicenow". This enables cross-matching between entity domains (e.g., "easycloud.cloud") and transaction vendor names (e.g., "Easycloud Inc-prod") while preventing false positives from generic terms or wrong-position brand mentions.

**Performance Optimizations:** Implemented memoization and pre-computation of entity normalization tokens to improve processing time for large snapshots.

**Traffic Light Provisioning:** A fail-closed system for asset provisioning with statuses: ACTIVE, REVIEW, QUARANTINE, BLOCKED, RETIRED, IGNORED.

**UI Design:** Adheres to the AutonomOS palette, featuring cyan and purple accents, a dark slate foundation, and the Quicksand font.

**Quality Guardrails:** Emphasizes semantic preservation, avoidance of "cheating," real-world proof via before/after outputs, and negative test inclusion. Designed to "fail loudly."

## External Dependencies
-   **Python 3.11**
-   **FastAPI** with **Pydantic v2**
-   **PostgreSQL** persistence via **asyncpg**
-   **Uvicorn** server
-   **httpx** for async HTTP communication with Farm
-   **Farm Integration**: Integrates with Farm for snapshot ingestion and reconciliation.