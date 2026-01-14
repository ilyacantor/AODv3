# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system designed to ingest raw enterprise evidence. Its primary function is to generate an Asset Catalog, a Run Log, and Explainable Findings by identifying and classifying enterprise assets without pre-adjudicated labels. The system aims to provide a clear, auditable, and deterministic view of an organization's digital footprint for robust asset management and risk mitigation. It prioritizes evidence-only decisions and full explainability.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
AOS Discover operates on core principles including no ground truth ingestion, no ML/anomaly scores, determinism, and evidence-only decisions, distinguishing between assets and artifacts to prevent asset count inflation.

The system processes data through a 7-stage sequential pipeline: Validation, Normalization, Indexing, Correlation, Admission, Artifact Handling, and Findings Generation.

**Governance Trinity:** Assets are classified as "Shadow" if they lack Visibility (CMDB registration), Validation (IdP presence), or Control (managed lifecycle). The system rejects the concept of "Grey IT."

**Derived Classifications:**
-   **Activity Status**: RECENT (active within 90 days), STALE (inactive beyond 90 days), or NONE.
-   **Anchored Predicate**: An asset is "anchored" if it has an IdP, CMDB, finance, or cloud resource match.
-   **Shadow Asset**: Ungoverned (no IdP AND no CMDB) AND RECENT activity.
-   **Financial Anchor Governance Gap**: Shadow asset with ongoing finance.
-   **Zombie Asset**: Governed (has IdP OR has CMDB) AND STALE activity AND ongoing finance.
-   **Parked Asset**: Ungoverned (no IdP AND no CMDB) AND STALE activity.

**Governance Policy:** `is_governed = has_idp OR has_cmdb`.

**Key Technical Implementations & Features:**
-   **Central Policy Switchboard:** All admission and classification policy logic is externalized to `config/policy_master.json`. Operators can control policy switches and thresholds via the web UI at `/switchboard`. Changes automatically notify Farm via webhook when `auto_notify_on_change` is enabled.
-   **Policy Categories:**
    - Activity Windows (discovery, zombie detection, default)
    - Finance Thresholds (minimum spend, gap thresholds)
    - Admission Gates (noise floor, SSO/CI/lifecycle requirements)
    - Scope Toggles (infrastructure inclusion, policy engine, domain merge)
    - Fuzzy Matching (edit distance, ratio, name length)
    - Vendor Inference (max confidence)
    - Query Limits (samples, rejection, query limits)
    - Exclusion Lists (custom, banned, infrastructure, corporate domains)
    - Farm Sync (webhook URL, auto-notify, sync interval)
-   **Admission Gates:** Finance alone is insufficient for asset admission; it requires corroboration with governance or sufficient discovery.
-   **Domain Normalization:** Standardizes domain names to eTLD+1 and collapses alias domains, including robust extraction from URLs.
-   **Tenant Token Indexing:** Extracts and indexes tenant tokens from subdomain patterns for cross-matching.
-   **Correlation Consistency:** Ensures uniform domain normalization across all correlation phases.
-   **Activity Status & Zombie Detection:** Calculates activity status relative to the snapshot timestamp, incorporating both Discovery observations and IdP last_login_at timestamps. It uses TLD-aware domain matching for IdP governance and activity inheritance. Finance timestamps are excluded from activity calculations.
-   **Domain Recovery:** Recovers entity domains from correlated plane records when discovery observations lack domain fields, utilizing a fallback chain including hostname and URI.
-   **Cross-Domain Correlation:** Enables correlation between entities with different domains sharing the same brand using first-token and collapsed hyphenated brand matching.
-   **Multi-Domain Identifiers:** Assets include all domains from correlated plane records in their identifiers for reconciliation, with comprehensive domain extraction from plane records. Rejected assets are no longer classified as shadows.
-   **Indexing Enhancements:** Extracts and indexes base names from registered domains and vendor names from finance transactions.
-   **Token-Based Finance Correlation:** Uses token-based matching for finance transactions based on domain base tokens and vendor names, with post-processing to expand finance records for complete vendor data.
-   **Discovery Sources Single Source of Truth:** `discovery_sources` is the canonical source for `HAS_DISCOVERY`, ensuring consistent reconciliation labels.
-   **Performance Optimizations:** Utilizes memoization and pre-computation for entity normalization tokens.
-   **Traffic Light Provisioning:** A fail-closed system for asset provisioning with various statuses.
-   **UI Design:** Adheres to the AutonomOS palette with cyan and purple accents, a dark slate foundation, and the Quicksand font.
-   **Quality Guardrails:** Emphasizes semantic preservation, real-world proof, and negative test inclusion for robust system behavior.

## External Dependencies
-   Python 3.11
-   FastAPI with Pydantic v2
-   PostgreSQL persistence via asyncpg
-   Uvicorn server
-   httpx for async HTTP communication
-   Farm Integration for snapshot ingestion and reconciliation