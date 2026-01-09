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
-   **Activity Status & Zombie Detection:** Accurate calculation of activity status based on observation and plane timestamps, crucial for identifying zombie assets. Fail-safe to "CLEAN" if no activity timestamps are available. **Snapshot Time Reference (Jan 2026):** Activity status (RECENT/STALE) is now calculated relative to the snapshot's generated_at/created_at timestamp, not wall-clock time. This ensures consistent reconciliation results regardless of when the snapshot is processed. **IdP Activity Integration (Jan 2026):** Activity is now calculated from BOTH Discovery observations AND IdP last_login_at timestamps, aligning with Farm's definition that "Activity = Network Visibility OR Authentication Success". Cross-IdP aggregation uses IdP NAME as the grouping key (e.g., "Maxflow" groups maxflow.ai, maxflow.org) - this is safe because IdP names are vendor-specific, unlike shared domains. **Critical Fix (Jan 2026):** When an asset matches to an IdP record, the system now ALWAYS checks the aggregated family max timestamp and uses whichever is newer. This ensures assets matched to stale sibling records (e.g., maxflow.ai with Feb 2025 login) inherit recent activity from other family members (e.g., maxflow.org with Dec 2025 login). Generic names (app, portal, admin, login, sso, auth, api, web, test, etc.) are blocklisted to prevent false aggregation. **Finance Exclusion from Activity (Jan 2026):** Finance timestamps (finance_last_transaction_at) are explicitly EXCLUDED from latest_activity_at calculation. Finance transactions are billing events, not usage evidence. Activity = Network Visibility (discovery/cloud) OR Authentication Success (IdP login). This prevents assets with stale IdP/discovery but recent finance from being falsely classified as RECENT instead of STALE.
-   **Domain Recovery:** Recovers entity domains from correlated plane records (IdP, CMDB, Cloud, Finance) when discovery observations lack domain fields. **Hostname Extraction (Jan 2026):** Domain resolution now checks `obs.hostname` field as a fallback when `obs.domain` is missing. Priority order: domain → hostname → uri → name (as domain) → name (vendor lookup) → vendor (lookup). This fixes KEY_NORMALIZATION_MISMATCH for observations that store domain info in the hostname field.
-   **Cross-Domain Correlation (Jan 2026):** Enables correlation between entities with different domains that share the same brand. Uses dual matching strategy: (1) First-token match for environment suffixes (e.g., "flowbase-internal.com" ↔ "flowbase.ai"), and (2) Collapsed match for hyphenated brands (e.g., "service-now.com" ↔ "servicenow.com"). Requires ≥4 char tokens to prevent false positives.
-   **Multi-Domain Identifiers (Jan 2026):** Assets now include ALL domains from correlated plane records (IdP, CMDB, etc.) in their identifiers.domains list. This enables Farm reconciliation to match assets by any domain variant, resolving KEY_NORMALIZATION_MISMATCH for zombie detection.
-   **Late-Binding Domain Merge (Jan 2026):** Now DISABLED (was causing issues with multi-tenant domain collapsing and governance evidence loss). Feature intended to merge assets sharing the same registered domain (eTLD+1) AFTER admission but was rolled back due to negative impact on zombie accuracy.
-   **Policy Updates (Jan 2026):** Removed tiktok.com from BANNED_DOMAINS (it's a common marketing platform, not policy-forbidden). Added workers.dev to DOMAIN_TO_VENDOR mapping for Cloudflare Workers domain resolution.
-   **Alias Keys Expansion (Jan 2026):** Reconciliation output (`emit_actual_results`) now builds `alias_keys` from ALL domain variants including `identifiers.domains`, `all_domain_variants`, and `registered_domain`. Both `asset_details.alias_keys` and `evidence_summary.alias_keys` are populated with the expanded list for BOTH admitted AND rejected assets. Rejected asset alias_keys are normalized to lowercase with proper type checking. This enables Farm to look up AOD assets by any domain variant, not just the primary asset key, resolving KEY_NORMALIZATION_MISMATCH where AOD has domain evidence but doesn't use it as the canonical key. **Systemic Rejection Domain Fix (Jan 2026):** Rejection records in pipeline_executor.py now include complete plane-extracted domain information: (1) `_extract_all_domains_from_correlation()` populates the `domains` list with all plane domains (IdP, CMDB, Cloud, Finance), (2) `_extract_domain_from_correlation()` recovers canonical domain from plane records, (3) `extract_registered_domain()` computes proper eTLD+1, (4) fallback to first plane domain if candidate has no domain. This ensures rejected assets can build proper alias_keys for Farm matching.
-   **Indexing Enhancements:** Extracts and indexes base names from registered domains and vendor names from finance transactions to improve correlation.
-   **Token-Based Finance Correlation:** Uses token-based matching for finance transactions. Requirements: (1) domain base token ≥4 chars, (2) NOT in GENERIC_TOKENS blocklist (cloud, data, online, digital, software, service, etc.), (3) domain base must match the FIRST token of vendor name (primary brand). VENDOR_PREFIXES skipped: the, a, an, team, inc, corp, llc, ltd, co, by. Hyphen normalization collapses "service-now" → "servicenow". This enables cross-matching between entity domains (e.g., "easycloud.cloud") and transaction vendor names (e.g., "Easycloud Inc-prod") while preventing false positives from generic terms or wrong-position brand mentions.
-   **Discovery Sources Single Source of Truth (Jan 2026):** Eliminated split-brain in discovery evidence by making `discovery_sources: list[str]` the canonical source for HAS_DISCOVERY. All code paths now derive has_discovery from this field: (1) admission.py sets discovery_sources from build_discovery_footprint() and derives lens_coverage.discovery from it, (2) decision_trace.py derives HAS_DISCOVERY from asset.discovery_sources, (3) derived_classifications.py uses asset.discovery_sources instead of recomputing from evidence_refs. Runtime invariants enforce consistency: lens_coverage.discovery must equal bool(discovery_sources). This ensures consistent reconciliation labels between AOD and Farm.

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