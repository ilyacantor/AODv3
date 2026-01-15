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

**Governance Policy:** `is_governed = has_idp OR has_cmdb OR vendor_governed`.

**Vendor Governance Propagation (Stage 3 - Jan 2026):**
-   Farm-style vendor governance propagation using `VENDOR_DOMAIN_SETS` and `DOMAIN_TO_VENDOR` mappings.
-   Seeds from authoritative matches only: `lens_coverage.idp=True` or `lens_coverage.cmdb=True` (gate-passed).
-   Propagates: All assets whose registered domain maps to a seeded vendor get `vendor_governed=True`.
-   Guardrails: Does NOT add domains, does NOT seed from heuristic matches, is fully traceable via `vendor_governance_trace`.
-   Example: outlook.com governed via IdP → office.com/sharepoint.com get `vendor_governed=True` (same vendor "Microsoft").

**Authoritative vs Heuristic Match Quality:**
-   CMDB and IdP are authoritative truth sources for governance decisions.
-   An asset is governed only if there exists at least one CMDB or IdP record that explicitly passes all governance gates via an AUTHORITATIVE match.
-   **AUTHORITATIVE** match methods: `domain`, `uri`, `canonical_name` - can assert governance.
-   **HEURISTIC** match methods: `fuzzy`, `contains`, `vendor`, `domain_vendor`, `vendor_fallback`, `name_contains_domain_token`, `normalization_token`, `cross_domain_brand` - enrichment only, cannot assert governance.
-   If a record exists but fails gates (or was matched heuristically), the asset is explicitly NOT governed.
-   Heuristics may generate hypotheses and enrichment signals but may never assert or override governance or classification outcomes.

**TLD Variant Identity Fix (Jan 2026):**
-   **Core Invariant**: Entity identity = registered domain (eTLD+1) ONLY. Cross-TLD matches (e.g., netcloud.com vs netcloud.io) are relationship metadata, NOT identity merge.
-   **RelatedDomainVariant**: New dataclass to store cross-TLD relationships as edges, not identity. Fields: entity_domain, related_domain, match_basis, record_id, plane.
-   **Cross-TLD Gate**: Cross-domain brand matching (`cross_domain_brand` match method) records variants as `related_domain_variants` enrichment, does NOT add to `contains_matches`.
-   **Domain Promotion Blocking**: `PROMOTION_ALLOWED_MATCH_METHODS` (authoritative only) and `PROMOTION_BLOCKED_MATCH_METHODS` (heuristics + cross-TLD). Domain promotion explicitly blocked for heuristic match methods.
-   **Late-Binding Merge Safety Rail**: Union-find in asset_identity.py groups by primary domain within each registered domain. Merges blocked when primary registered domains differ (`CROSS_TLD_MERGE_BLOCKED` reason code).
-   **Documentation**: Full details in `docs/TLD_VARIANT_FIX.md`, unit tests in `tests/test_tld_variant_isolation.py`.
-   **Impact**: Eliminates 82 false positives (63% from TLD variant merging, 32% from key normalization).

**Governance Correlation Fixes (Jan 2026):**
-   **Registered Domain Fallback**: When exact domain lookup fails in Pass 1, tries registered domain (eTLD+1) as fallback. This enables matches like entity "maxsoft.org" matching CMDB "api.maxsoft.org" with authoritative "domain" method.
-   **Discovery Provenance Preservation**: Domains recovered from correlation retain provenance="discovery" when entity has discovery observations, ensuring v2 key selection uses the correct discovery domains.
-   **Domain Base Name Matching**: When Pass 2 canonical_name match fails and entity has domain, tries matching domain base name (e.g., "slack" from "slack.com") against record names. This fixes FP shadows where IdP/CMDB records have app name but no external_ref/domain. Match method remains "canonical_name" (authoritative) for governance.
-   **Test Coverage**: 35 tests including TLD isolation, match method classification, registered domain fallback, and domain base name matching validation.

**Reason Code Semantics (Jan 2026 Fix):**
-   `HAS_CMDB` / `HAS_IDP` = Direct authoritative match only (domain/uri/canonical_name that passes gates)
-   `VENDOR_GOVERNED` = Governance via vendor family propagation (explicit rule, can flip classification)
-   Classification uses: `is_governed = HAS_IDP OR HAS_CMDB OR VENDOR_GOVERNED`
-   But reason codes distinguish the SOURCE of governance for audit trail
-   `lens_coverage.idp/cmdb` = direct matches only, NOT from vendor propagation
-   `lens_coverage.vendor_governed` = governance inherited from vendor family
-   Heuristic correlations preserved in `lens_match_debug` for enrichment but don't set HAS_CMDB/HAS_IDP

**Key Normalization (Stage 4 - Jan 2026):**
-   Infrastructure/service domains produce STABLE STANDALONE asset keys (not collapsed to vendor domain)
-   Domains removed from `ALIAS_DOMAINS_TO_COLLAPSE`: outlook.com, gstatic.com
-   Domains already preserved as standalone: office.com, cloudfront.net, awsstatic.com
-   Each domain produces its own canonical key for accurate Farm reconciliation
-   Fixes KEY_NORMALIZATION_MISMATCH errors for these infrastructure domains

**Key Selection Contract v2.0 (Jan 2026):**
-   **Formal contract**: `docs/contracts/KEY_SELECTION_CONTRACT.md` - defines deterministic rules for Farm alignment
-   **Source**: Discovery observations ONLY (CMDB/IdP domains are reference/enrichment)
-   **Canonical Key**: Lexicographic sort on collapsed candidates (NOT list position)
-   **Alias Collapse**: Only domains in `ALIAS_DOMAINS_TO_COLLAPSE` collapse to vendor domain
-   **Standalone Domains**: outlook.com, gstatic.com, office.com, cloudfront.net produce their own keys
-   **Policy Exclusions**: BANNED_DOMAINS cause rejection (emit in `expected.rejected`), no key generated
-   **Forbidden**: Using domains[0], CMDB external_ref URLs, "first observation wins"
-   **Alignment**: Farm and AOD use same PSL, same collapse list, same lexicographic tie-breaker

**Identity Model & Key Strategy (Jan 2026 CTO Guidance):**
-   **Domain Provenance Tracking**: `identifiers.domain_provenance` maps each domain to its source: `discovery`, `cmdb`, `idp`, `vendor_map`, or `inferred`
-   **CMDB Domain Promotion**: Authoritative CMDB domains (from `record.domain` field) can be added to `identifiers.domains` if they pass validation gates. external_ref URLs remain in `reference_domains` only (Stage 1 fix preserved)
-   **Generic Collision Roots**: High-collision eTLD+1 domains (cdn.com, edge.com, cloud.com, etc.) suppressed from identity unless explicitly anchored. Configurable via `generic_collision_roots` policy category
-   **Key Strategy Versioning**: `key_strategy_version` policy (v1/v2) controls canonical key generation. v2 uses domain provenance priority (idp → cmdb → discovery → vendor → fallback)
-   **Reconciliation Mapping Layer**: `anchor_type` (IDP, CMDB, FINANCE, CLOUD, DISCOVERY, NONE), `absence_flags`, and `entity_key_v2` fields enable Farm reconciliation vocabulary alignment
-   **Governance Invariant**: CMDB domain promotion only bypasses filters when MATCHED (not AMBIGUOUS) + authoritative match method + cmdb_admitted=True

**Stage 1 Metrics (CMDB External Ref Domain Leakage):**
-   CMDB external_ref domains stored in `reference_domains` (enrichment only)
-   NOT added to `identifiers.domains` (prevents false key generation)
-   Metrics available via `/api/runs/{run_id}/derived` → `stage1_metrics`
-   Verification: `domains_in_both_identity_and_reference` must be 0

**Key Technical Implementations & Features:**
-   **Central Policy Switchboard:** All admission and classification policy logic is externalized to `config/policy_master.json`. Operators can control policy switches and thresholds via the web UI at `/switchboard`. Changes automatically notify Farm via webhook when `auto_notify_on_change` is enabled.
-   **Policy Impact Panel (Jan 2026):** The Policy Switchboard now displays a Policy Impact panel showing which domains are blocked by each policy rule and their counts. Categories include: CDN/Static Hosts, Vendor Portals, Dev/Build Infra, Custom, Admission Gates, and Other. Operators can click categories to see detailed lists. API: `GET /api/v1/policy/impact?run_id=optional`.
-   **Semantic Infrastructure Domain Handling (Jan 2026):**
    - `shared_infrastructure_domains`: CDNs, static hosts, internet plumbing (cloudfront.net, gstatic.com, akamai.net) - observe only
    - `vendor_root_portals`: Vendor landing pages (office.com, microsoft.com, google.com) - policy choice to exclude
    - `dev_build_infrastructure`: Build/dev tools (npm, github, docker) - typically excluded
    - Business SaaS (TikTok, Slack, Zoom, ServiceNow) NOT excluded by default - can be legitimate shadow IT
    - Mode options: "exclude" (default), "observe_only", "include"
-   **Policy Categories:**
    - Activity Windows (discovery, zombie detection, default)
    - Finance Thresholds (minimum spend, gap thresholds)
    - Admission Gates (noise floor, SSO/CI/lifecycle requirements)
    - Scope Toggles (infrastructure inclusion, policy engine, domain merge)
    - Fuzzy Matching (edit distance, ratio, name length)
    - Vendor Inference (max confidence)
    - Query Limits (samples, rejection, query limits)
    - Infrastructure Domain Handling (shared infra, vendor portals, dev/build infra)
    - Custom Exclusions (operator-defined exclusion list)
    - Corporate Root Domains (organization's own domains)
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