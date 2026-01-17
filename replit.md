# AOS Discover - AutonomOS Discovery Module

## Overview

**Why You'll See "Farm"**

Complex enterprise systems are easy to demo and hard to trust.

AOS Farm is our stress-test engine. It validates the platform against a theoretical space of ~300,000 state combinations by generating realistic enterprise chaos:

- **17,000 Asset Permutations**: From standard servers to "zombie" instances.
- **37 Edge Case Categories**: Specifically targeting governance forks and data quality failures.
- **800,000 Rule Evaluations**: Proving stability at scale.

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

**CMDB Authoritative Recovery (Jan 2026 - Phase B):**
-   **CMDBConfigItem.domains[]**: New array field to hold all authoritative domains from Farm.
-   **PlaneIndex Authoritative Indexes**: Added `by_canonical_domain` and `by_domains_array` separate indexes for authoritative CMDB correlation.
-   **CMDB Indexing Expansion**: `canonical_domain` and `domains[]` are now indexed SEPARATELY (not as fallback), while still mirrored to `by_domain` for backward compatibility.
-   **Deterministic Lookup Order**: CMDB correlation uses authoritative-only paths in order: (1) canonical_domain == D, (2) D ∈ domains[], (3) verified_alias_domain(D) == canonical_domain.
-   **Runtime Governance Assertion**: `check_idp_admission` blocks heuristic match methods from asserting HAS_IDP. Fail-safe defaults unknown methods to heuristic.
-   **Legacy Product Standalone**: hipchat.com and yammer.com treated as standalone domains (legacy products, not technical aliases) for proper zombie detection.
-   **Test Coverage**: 76 tests validating TLD isolation, governance invariants, heuristic blocking, and CMDB authoritative recovery.

**Category 5 FP Fix - Entity Domain Evidence Requirement (Jan 2026):**
-   **Problem**: Vendor name inference (e.g., "db-mongo" → mongodb.com) created false entities without actual discovery domain evidence.
-   **Fix**: Removed vendor name → domain inference from `resolve_domain_from_observation()` for entity creation.
-   **New Rule**: Observations must have domain/hostname/uri evidence to create entities.
-   **Vendor Inference**: Still available via `_lookup_vendor_domain()` for enrichment/correlation, but NOT for entity creation.
-   **Verification**: Old run had 720 assets; new run has 717 assets (3 FPs eliminated: mongodb.com, elasticsearch.com, sentry.io).
-   **Iron Dome**: Observations without domain evidence now rejected at iron_dome stage (338 → 499 rejections).
-   **Test Coverage**: 78 governance tests + updated tests ensure name-only observations are correctly rejected.

**Reconciliation Milestone (Jan 2026):**
-   **Combined Accuracy**: 98.7% across all tested snapshots
-   **Classification Accuracy**: 98.0% (649/657 correct classifications)
-   **Admission Accuracy**: 99.2% (877/884 correct admission decisions)
-   **Zombie Detection**: 100% (45/45 zombies correctly identified)
-   **Shadow Detection**: 98.7% (604/612 shadows matched)
-   **Remaining Discrepancies**: 5 IdP token edge cases + 2 Zoom TLD variants (documented policy differences)
-   **Validation**: Tested across multiple Farm snapshot combinations with consistent results

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

**Farm Cold Start Support (Jan 2026):**
-   **Timeout & Retry**: FarmClient uses 25s timeout with automatic retry on transient errors (502/503/504, network errors, timeouts).
-   **JSON-Only Responses**: Backend farm routes always return JSON (never HTML) with structured error payloads (`{ok: false, error: "FARM_WAKING_OR_DOWN"}`).
-   **UI Feedback**: Shows "Waking up Farm..." during fetch, displays "Farm unavailable" on errors with robust JSON parsing (handles non-JSON responses gracefully).
-   **Environment Variables**: Uses `FARM_URL_PROD` as canonical source (in Secrets) with `FARM_URL` fallback for backward compatibility.

**Snapshot Drift Detection (Jan 2026):**
-   **Architecture**: Plane data (IdP/CMDB/Cloud/Finance) is built in-memory from `snapshot.planes` each run, NOT persisted in separate DB tables. Asset records persist with `lens_match_debug` containing matched record IDs.
-   **Drift Risk**: If Farm regenerates a snapshot after a run was created, the asset's correlation data (IdP matches, etc.) becomes stale. The matched records may no longer exist.
-   **Snapshot Fingerprint Tracking**: New runs store `provenance.snapshot_fingerprint` to detect when Farm regenerates snapshots.
-   **Drift Check Endpoint**: `GET /api/debug/snapshot-drift-check?run_id=X` compares stored vs current fingerprint to detect snapshot changes.
-   **Invariant Check Endpoint**: `GET /api/debug/catalog-invariant-check?run_id=X` validates all assets have valid admission basis (discovery OR idp OR cmdb OR finance OR cloud).
-   **Detection Status Codes**: `OK` (no drift), `DRIFT_DETECTED` (snapshot changed), `NO_STORED_FINGERPRINT` (legacy run).

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