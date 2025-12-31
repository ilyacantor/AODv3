# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence to generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets. This provides a clear, auditable view of an organization's digital footprint, supporting robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

AOS Discover follows a strict architectural design based on several core principles:
- **No ground truth ingestion**: Rejects fields like `is_shadow_it` or `ground_truth`.
- **No ML/anomaly scores**: Relies solely on deterministic rules and explainable correlation.
- **Deterministic**: Ensures identical outputs for the same snapshot and configuration.
- **Evidence-only decisions**: Admission and findings are derived exclusively from plane evidence.
- **Assets vs. Artifacts**: Distinguishes between actual assets and artifacts (dashboards, reports), preventing inflation of asset counts.

The system uses a 7-stage sequential pipeline for processing:
1. **Validation**: Schema validation of input snapshots.
2. **Normalization**: Standardizing names and domains.
3. **Indexing**: Building plane indexes for efficient lookups.
4. **Correlation**: Three-pass correlation of entities.
5. **Admission**: Applying criteria for asset inclusion.
6. **Artifact Handling**: Processing non-asset related data.
7. **Findings Generation**: Producing explainable findings.

**Governance Trinity (Dec 2025):**
Shadow IT is defined by the absence of explicit sanctioning, not by malicious intent or utility. Any asset that fails the Governance Trinity is Shadow:
- **Visibility**: Registered in CMDB
- **Validation**: Present in IdP (sanctioned/SSO)
- **Control**: Managed lifecycle tied to owner

Finance presence does NOT equal governance. You can pay for unsanctioned tools. There is no "Grey IT" - binary classification only.

**Derived Classifications:**
- **Activity Status**: Classifies assets as RECENT (active within 90 days), STALE (inactive beyond 90 days), or NONE (no activity timestamps).
- **Anchored Predicate**: An asset is "anchored" if it has an IdP, CMDB, finance, or cloud resource match. Used for zombie eligibility.
- **Shadow Asset**: Ungoverned (NOT has_idp AND NOT has_cmdb) AND RECENT activity. Finance does NOT exempt from shadow.
- **Financial Anchor Governance Gap**: Shadow asset with ongoing finance - needs governance review despite being paid for.
- **Zombie Asset**: Governed (has_idp OR has_cmdb) AND STALE activity AND ongoing_finance. "Paying for something you don't use" - requires ongoing spend. Without ongoing finance, stale governed assets are just inactive (not wasting money).
- **Parked Asset**: Ungoverned (NOT has_idp AND NOT has_cmdb) AND STALE activity. Non-actionable since nothing to deprovision.

**Dec 2025 - Governance Policy (OR Logic):**
Governance is defined as: `is_governed = has_idp OR has_cmdb`
- IdP presence alone = governed
- CMDB presence alone = governed
- Neither = ungoverned (shadow if active)

This policy applies consistently across all admission, discovery, recognition, and classification logic. There are NO instances where both IdP AND CMDB are required.

**Dec 2025 Logic Fixes:**
1. **Finance Admission Gate**: Finance alone is NOT sufficient for admission. Finance can only contribute to admission if paired with:
   - Governance (IdP or CMDB), OR
   - Sufficient discovery (≥2 sources)
   Finance-only assets with minimal discovery (<2 sources) are rejected. This prevents low-confidence finance-only assets from cluttering the catalog as false positive shadows.
2. **Post-Correlation Domain Recovery**: When entities lack a domain from normalization but have valid plane correlations, the domain is recovered from match keys (priority: IdP→CMDB→Cloud→Finance) and persisted onto `entity.domain` before admission gates.
3. **Generic Subdomain Stripping**: `normalize_domain()` now uses `extract_registered_domain()` (PSL-backed) to strip ALL subdomains to eTLD+1. Example: `api.primebox.io` → `primebox.io`, `login.microsoft.com` → `microsoft.com`. This fixes KEY_NORMALIZATION_MISMATCH errors (174 errors) by ensuring discovery and CMDB domains normalize to the same base domain.
4. **Alias Domain Normalization**: After subdomain stripping, ALIAS_DOMAINS_TO_COLLAPSE further normalizes known aliases. Example: `microsoftonline.com` → `microsoft.com`. Primary domains like `atlassian.net`, `notion.so`, `sentry.io` are preserved as legitimate SaaS keys.
5. **Tenant Token Indexing**: IdP/CMDB plane indexes now extract and index tenant tokens from subdomain-based patterns. Example: `flowsoft.okta.com` → tenant token `flowsoft` indexed in `by_name_words`. This enables cross-matching where discovery domain `flowsoft.org` (token `flowsoft`) matches IdP tenant `flowsoft.okta.com`. Fixes NO_IDP/NO_CMDB misclassifications.
6. **Zombie vs Parked**: CMDB matching now works correctly since both sides normalize consistently. Stale assets with CMDB entry are Parked (owned but inactive), not Zombie. This fixes FP_FROM_PARKED (36 false positives). Only orphaned (no CMDB owner) stale assets become Zombies.
7. **Correlation Normalization Consistency (Dec 2025)**: Fixed `correlate_entities.py` to use `normalize_domain()` instead of `extract_registered_domain()` in vendor validation, domain-based vendor matching, and precomputed entity data. This ensures the correlation phase uses the same normalization pipeline (including alias mapping and PaaS preservation) as plane index building, eliminating KEY_NORMALIZATION_MISMATCH for long-tail domains like `api.netforce.io`.
8. **Governance Admission Policy (Dec 2025)**: IdP or CMDB presence is sufficient for admission - no discovery corroboration required. If an asset is registered in governance systems, it should be admitted to the catalog.
9. **Activity Status Classification Fix (Dec 2025)**: Fixed `_build_policy_asset_data()` in `pipeline_executor.py` to calculate `is_active` from observation timestamps instead of hardcoding `True`. Assets with observations older than 90 days are now correctly classified as STALE, enabling zombie detection (governed + stale = zombie).
10. **TLD Recognition Fix (Dec 2025)**: Expanded `_looks_like_domain()` in `normalize_observations.py` to recognize additional TLDs including `.ai`, `.tech`, `.biz`, `.info`, `.xyz`, `.me`, etc. This fixes KEY_NORMALIZATION_MISMATCH for domains like `hubforce.tech`, `ultraly.ai` that were not being recognized as domains when passed via observation name field.
11. **Post-Correlation Domain Recovery (Dec 2025)**: When discovery observations lack domain fields (e.g., name="OpenSuite"), entities are keyed by name. After correlation, if matched IdP/CMDB/Cloud records have domains, we now adopt that domain as the entity's canonical key via `_recover_domain_from_planes()`. Priority: IdP→CMDB→Cloud→Finance. Fixes KEY_NORMALIZATION_MISMATCH for assets like `opensuite.net` where the name-only entity correlated to governance records with domains.
12. **Plane Timestamp Fallback for Activity (Dec 2025)**: When discovery observations lack timestamps, `_build_policy_asset_data()` now extracts activity timestamps from correlated plane records (IdP: last_login/last_access, CMDB: last_seen, Cloud: last_activity, Finance: last_invoice_date) via `_extract_plane_timestamps()`. This ensures `is_active` can be calculated even after domain recovery re-keys entities. Fixes zombie detection where governed stale assets were marked as clean due to missing observation timestamps.
13. **Classification Logic Alignment (Dec 2025)**: Unified all classification logic across the codebase to match Policy Engine exactly:
    - **is_governed = has_idp OR has_cmdb** (single definition used everywhere)
    - **SHADOW = NOT is_governed AND activity_status==RECENT**
    - **ZOMBIE = is_governed AND activity_status==STALE AND has_ongoing_finance** ("paying for something you don't use")
    - **PARKED = NOT is_governed AND activity_status==STALE** (informational only)
    - Removed conflicting "Governance Trinity" (AND) logic from derived_classifications.py and aod_agent_reconcile.py
    - Zombie requires ongoing_finance - stale governed assets without spend are just inactive, not wasting money
14. **Fail-Safe to Clean (Dec 2025)**: When no activity timestamps are available (from observations or plane records), assets fail-safe to CLEAN instead of being classified as STALE. Principle: **"You can't prove abandonment without evidence."** This prevents false positive zombie classification when timestamp data is missing. Only assets with PROVEN stale activity (timestamps > 90 days old) can become zombies.
15. **Cloud Reason Codes Removed (Dec 2025)**: Removed `HAS_CLOUD`/`NO_CLOUD` reason codes from reconciliation output. Cloud presence is NOT used in shadow/zombie/parked classification (governance = IdP OR CMDB only). Including cloud codes in reason output was causing confusion where assets appeared to be flagged as zombie "because of NO_CLOUD" when cloud is actually irrelevant to classification. Cloud presence is still used for the "anchored" predicate but not emitted as a reason code.
16. **Evidence Domain Extraction (Dec 2025)**: Fixed KEY_NORMALIZATION_MISMATCH by extracting domains from evidence_refs and adding them to all_domain_variants. When assets are keyed by name but have correlated CMDB/IdP records with domains, those domains now appear in domain_aliases for Farm to match against.
17. **Domain Recovery from Matched Records (Dec 2025)**: Enhanced `_extract_domain_from_correlation()` in admission.py to extract domains directly from matched plane records, not just match_key. Priority order:
    - **IdP matched_records[].domain** - Most authoritative for active SSO domains
    - **CMDB matched_records[].domain** - IT-registered infrastructure domains
    - **Fallback: match_key** - For direct domain-based matches
    This fixes zombies being missed when entities are keyed by name (e.g., "rapidlabs") but have CMDB/IdP records containing the actual domain (e.g., "rapidlabs.org"). Previously, name-based matches set match_key to the entity name (no dot), so domain recovery failed.

**Performance Optimizations (Dec 2025):**
The correlation pipeline was optimized to reduce large snapshot processing time:
1. **Memoization**: Added `@functools.lru_cache(maxsize=10000)` to:
   - `normalize_string()` in normalize_observations.py
   - `extract_registered_domain()` in vendor_inference.py
   - `get_normalization_token()` in utils/normalization.py
   - `_levenshtein_distance()` in correlate_entities.py
2. **Pre-computation**: Entity normalization tokens (registered_domain, domain_token, canonical_vendor, normalization_token) are computed once before plane correlation loop via `PrecomputedEntityData` dataclass.
3. **Timing Instrumentation**: Per-stage timing logged for precompute, idp, cmdb, cloud, finance phases to identify remaining bottlenecks.

**Traffic Light Provisioning**: A fail-closed system for asset provisioning, controlling flow to DCL with statuses like ACTIVE (Green), REVIEW (Amber), QUARANTINE (Red), BLOCKED, RETIRED, and IGNORED.

**UI Design**: Adheres to the AutonomOS palette, featuring cyan and purple accents, a dark slate foundation, and the Quicksand font.

**Quality Guardrails**: Emphasizes semantic preservation, avoidance of "cheating" (overwrites, silent fallbacks), real-world proof via before/after outputs, and negative test inclusion. The system is designed to "fail loudly" with explicit error statuses.

## External Dependencies
- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **PostgreSQL** persistence via **asyncpg**
- **Uvicorn** server
- **httpx** for async HTTP communication with Farm
- **Farm Integration**: Integrates with Farm for snapshot ingestion and reconciliation, acting as the source of raw evidence.