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
- **Shadow Asset**: Ungoverned (NOT both IdP AND CMDB) AND RECENT activity. Finance does NOT exempt from shadow.
- **Financial Anchor Governance Gap**: Shadow asset with ongoing finance - needs governance review despite being paid for.
- **Zombie Asset**: Anchored AND STALE activity AND NO registered owner (orphaned). CMDB presence = owned = not zombie.
- **Parked Asset**: STALE activity AND (has registered owner in CMDB OR not anchored). Owned but inactive, or non-actionable.

**Dec 2025 - Governance Trinity Enforcement:**
Shadow classification upgraded from `OR` to `AND` logic for fail-closed policy:
- **OLD (insecure)**: `is_governed = has_idp OR has_cmdb` - CMDB-only assets marked Clean
- **NEW (secure)**: `is_governed = has_idp AND has_cmdb` - Both required for governance

This fixes the security hole where CMDB-only assets (e.g., user manually enters Dropbox) were incorrectly marked as "Clean" when they should be Shadow IT. Now both IdP (Validation) AND CMDB (Visibility) are required for an asset to be considered governed.

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