# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system designed to ingest raw enterprise evidence. Its primary function is to generate an Asset Catalog, a Run Log, and Explainable Findings by identifying and classifying enterprise assets without pre-adjudicated labels. The system aims to provide a clear, auditable, and deterministic view of an organization's digital footprint for robust asset management and risk mitigation, prioritizing evidence-only decisions and full explainability. The project's ambition is to provide a complete and accurate picture of an organization's digital assets, distinguishing between assets and artifacts to prevent asset count inflation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
AOS Discover operates on core principles including no ground truth ingestion, no ML/anomaly scores, determinism, and evidence-only decisions. It processes data through a 7-stage sequential pipeline: Validation, Normalization, Indexing, Correlation, Admission, Artifact Handling, and Findings Generation.

**Governance Trinity & Classifications:** Assets are classified as "Shadow" if they lack Visibility (CMDB registration), Validation (IdP presence), or Control (managed lifecycle), rejecting the concept of "Grey IT." Derived classifications include Activity Status (RECENT, STALE, NONE), Anchored Predicate, Shadow Asset, Financial Anchor Governance Gap, Zombie Asset, and Parked Asset. The governance policy is defined as `is_governed = has_idp OR has_cmdb OR vendor_governed`.

**Vendor Governance Propagation:** The system propagates vendor governance using `VENDOR_DOMAIN_SETS` and `DOMAIN_TO_VENDOR` mappings, seeded from authoritative matches only (CMDB or IdP). This propagation is fully traceable and does not add new domains or seed from heuristic matches.

**Authoritative vs. Heuristic Matching:** CMDB and IdP are authoritative truth sources for governance. Authoritative match methods (`domain`, `uri`, `canonical_name`) can assert governance, while heuristic methods (`fuzzy`, `contains`, `vendor`, etc.) are for enrichment only and cannot assert or override governance or classification outcomes.

**TLD Variant Identity Fix:** Entity identity is strictly defined by the registered domain (eTLD+1). Cross-TLD matches are treated as `RelatedDomainVariant` metadata, not identity merges, preventing false positives from TLD variant merging. Domain promotion is blocked for heuristic match methods.

**Governance Correlation Fixes (Jan 2026):** Enhancements include:
-   **Registered Domain Fallback**: When exact domain lookup fails, tries eTLD+1 fallback for authoritative matching.
-   **Discovery Provenance Preservation**: Domains recovered from correlation retain provenance="discovery".
-   **Domain Base Name Matching**: Matches entity domain base (e.g., "slack" from "slack.com") against record names when canonical_name match fails.
-   **Canonical Domain Indexing**: Farm's `canonical_domain` field is now indexed for CMDB/IdP correlation.
-   **Alias Collapsing Alignment**: Fixed direction (zoom.us → zoom.com). Added atlassian.net, trello.com, bitbucket.org → atlassian.com, hipchat.com → atlassian.com, yammer.com → microsoft.com.
-   **Test Coverage**: 67 tests validating TLD isolation, match methods, correlation fixes, alias collapsing, and governance gate invariants.

**Governance Gate Hardening (Jan 2026 - Phase A):**
-   **Expanded AUTHORITATIVE_MATCH_METHODS**: Added 5 new authoritative methods: `verified_alias_domain`, `foreign_key`, `explicit_id`, `cmdb_domains_array`, `cmdb_canonical_domain`.
-   **HEURISTIC_MATCH_METHODS Set**: Explicit set of heuristic-only methods (`fuzzy`, `contains`, `vendor`, `domain_token_to_name`, `registered_domain_token`, `canonical_name_as_domain`). No overlap with authoritative set.
-   **Governance Invariant**: Unknown match methods default to heuristic (fail-safe). Heuristics produce candidates/enrichment only, NEVER HAS_IDP/HAS_CMDB.
-   **Debug Instrumentation**: AOD_DEBUG_MATCH env var logs per-plane match method classification. LensMatchDebug includes IDP_CANDIDATE/CMDB_CANDIDATE flags.
-   **PROMOTION_ALLOWED_MATCH_METHODS**: Updated to include all authoritative methods for domain promotion.

**Reason Code Semantics:** Reason codes like `HAS_CMDB`, `HAS_IDP`, and `VENDOR_GOVERNED` distinguish the source of governance for auditing, while `lens_coverage` fields reflect direct matches or inherited vendor governance.

**Key Normalization:** Infrastructure/service domains (e.g., `outlook.com`, `gstatic.com`, `office.com`) produce stable, standalone asset keys rather than collapsing to vendor domains, ensuring accurate reconciliation.

**Key Selection Contract v2.0:** A formal contract defines deterministic rules for Farm alignment, using discovery observations as the sole source. It specifies canonical key generation, alias collapsing, standalone domains, policy exclusions, and alignment with Farm using the same PSL, collapse list, and lexicographic tie-breaker.

**Identity Model & Key Strategy:** The system tracks domain provenance (`identifiers.domain_provenance`), allows authoritative CMDB domains to be promoted to `identifiers.domains`, suppresses generic collision roots, and uses `key_strategy_version` (v1/v2) for canonical key generation. A reconciliation mapping layer (`anchor_type`, `absence_flags`, `entity_key_v2`) aligns with Farm's vocabulary.

**AAM Blocking Logic (Jan 2026):** Finding types determine whether assets can connect to AAM (Asset & Access Management):
-   **BLOCKING findings (Red section):** `identity_gap`, `finance_gap`, `data_conflict` - AAM connection blocked by default
    - `identity_gap`: No IdP/SSO integration = no lifecycle control, no offboarding, no access auditability
    - `finance_gap`: Active spend without accountable owner = dangerous to enable integrations
    - `data_conflict`: Sources disagree on identity/ownership = cannot safely act
-   **NON-BLOCKING findings (Green section):** `cmdb_gap`, `governance_gap`, `duplication_risk` - Informational only
    - These are hygiene issues that don't prevent AAM connection
-   **Triage Sections:** Red = "Blocking — Cannot Connect", Yellow = "Review — Cost Optimization" (zombies), Green = "Informational — Non-Blocking"
-   **Override Support:** Blocking findings can be overridden with "warn only" mode per customer policy

**Key Technical Implementations & Features:**
-   **Central Policy Switchboard:** Externalizes all admission and classification policy logic to `config/policy_master.json`, allowing operators to control policies via a web UI (`/switchboard`) with webhook notifications to Farm.
-   **Policy Impact Panel:** Displays which domains are blocked by each policy rule and their counts, categorized by CDN/Static Hosts, Vendor Portals, Dev/Build Infra, Custom, Admission Gates, and Other.
-   **Semantic Infrastructure Domain Handling:** Configurable modes ("exclude," "observe_only," "include") for `shared_infrastructure_domains`, `vendor_root_portals`, and `dev_build_infrastructure`.
-   **Policy Categories:** Comprehensive policy control covering Activity Windows, Finance Thresholds, Admission Gates, Scope Toggles, Fuzzy Matching, Vendor Inference, Query Limits, Infrastructure Domain Handling, Custom Exclusions, Corporate Root Domains, and Farm Sync.
-   **Admission Gates:** Require corroboration with governance or sufficient discovery for asset admission, finance alone is not enough.
-   **Domain Normalization & Tenant Token Indexing:** Standardizes domain names and extracts tenant tokens for cross-matching.
-   **Activity Status & Zombie Detection:** Calculates activity based on Discovery observations and IdP timestamps, using TLD-aware domain matching.
-   **Domain Recovery & Cross-Domain Correlation:** Recovers entity domains from correlated plane records and enables correlation between entities with different domains sharing the same brand.
-   **Multi-Domain Identifiers:** Assets include all domains from correlated plane records.
-   **Indexing Enhancements:** Extracts base names from registered domains and vendor names from finance transactions.
-   **Token-Based Finance Correlation:** Uses token-based matching for finance transactions.
-   **Discovery Sources Single Source of Truth:** `discovery_sources` is the canonical source for `HAS_DISCOVERY`.
-   **Performance Optimizations:** Utilizes memoization and pre-computation.
-   **UI Design:** Adheres to the AutonomOS palette with cyan and purple accents, a dark slate foundation, and the Quicksand font.
-   **Quality Guardrails:** Emphasizes semantic preservation, real-world proof, and negative test inclusion.

## External Dependencies
-   Python 3.11
-   FastAPI with Pydantic v2
-   PostgreSQL (via asyncpg)
-   Uvicorn
-   httpx
-   Farm Integration