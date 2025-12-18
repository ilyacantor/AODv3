# AOD Fresh - AutonomOS Discover

## Overview

AOD Fresh is the discovery module of AutonomOS, an enterprise operating system. It ingests raw enterprise evidence and produces an Asset Catalog (systems only), a Run Log (audit trail), and Explainable Findings (rule-based, no ML/anomaly scores). The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels. Its core purpose is to accurately identify and classify enterprise assets based on observed evidence, contributing to a clear and auditable view of an organization's digital footprint.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles

- **No Ground Truth Ingestion**: Rejects banned fields (e.g., `is_shadow_it`) to ensure evidence-only processing.
- **No ML/Anomaly Scores**: Relies solely on deterministic rules and explainable correlation.
- **Deterministic**: Guarantees identical outputs for identical inputs with stable ordering.
- **Evidence-Only Decisions**: All admissions and findings are derived exclusively from raw evidence.
- **Assets vs. Artifacts**: Distinguishes systems (assets) from internal objects (artifacts) to prevent inflated asset counts.

### Pipeline Architecture

AOD Fresh uses a 7-stage sequential pipeline:
1.  `validate_snapshot.py`: Schema validation and banned field rejection.
2.  `normalize_observations.py`: Normalizes data and derives candidate entities.
3.  `build_plane_indexes.py`: Creates indexes for efficient correlation.
4.  `correlate_entities.py`: Performs five-pass correlation with disambiguation.
5.  `admission.py`: Applies criteria to determine assets.
6.  `artifact_handler.py`: Identifies and records artifacts.
7.  `findings_engine.py`: Generates deterministic findings.

### Finding Categories (Dec 2025)

Findings are split into two categories for clearer prioritization:

**Security Risks** (actionable, risk-bearing):
| Finding Type | Severity | Why Security Risk |
|--------------|----------|-------------------|
| identity_gap | HIGH | Asset bypasses IdP → no auth, no MFA, no deprovisioning |
| finance_gap | HIGH | Paying for undiscovered system → likely shadow IT |
| data_conflict | MEDIUM | Conflicting environment/state can mask prod exposure |

**Governance/Operational Findings** (hygiene, accuracy, readiness):
| Finding Type | Severity | Category |
|--------------|----------|----------|
| cmdb_gap | MEDIUM | Asset governance |
| governance_gap | LOW | Ownership / accountability |
| duplication_risk | MEDIUM | Data quality / ambiguity |

Sorting order: Category (security_risk first) → Severity (CRITICAL → HIGH → MEDIUM → LOW) → Finding type. The `category` field is `security_risk` or `governance_finding`. 

**UI Layout (Dec 2025):** Security Risks is now a standalone top-level KPI box (red color) alongside Assets, Shadow, and Zombie. Findings (governance/data quality) is also a top-level KPI. Artifacts and Ambiguous are now folded under Findings as sub-drill paths. The severity enum includes CRITICAL for the most severe issues.

### Correlation Disambiguation

The system uses specific codes (e.g., `MULTI_ENV`, `LEGACY`, `DUPLICATE`, `PARENT_VENDOR`, `UNRESOLVED`) to resolve multiple matches. Disambiguation is evidence-driven, requiring CMDB fields to support resolution; otherwise, matches remain `AMBIGUOUS`. Prevention mechanisms include `PARENT_VENDOR` to avoid incorrect vendor matching and `KNOWN_DISTINCT_PRODUCTS` blocklist for substring false positives (e.g., "box" vs. "dropbox"). Fuzzy matching handles typos with Levenshtein distance for names ≥4 characters.

### Data Planes

Evidence is sourced from 7 planes: Discovery, IdP, CMDB, Cloud, Endpoint, Network, and Finance.

### Derived Classifications

Shadow and Zombie classifications are derived post-pipeline:
-   **Shadow Asset**: Discovered + Active + Ungoverned (has discovery/cloud evidence, recent activity within 90 days, but NO IdP or CMDB presence).
-   **Zombie Asset**: Has IdP/CMDB presence but no recent activity (90-day window).

**Shadow Policy (Dec 2025):** Finance is NOT a trigger or gate for shadow classification. Shadow depends ONLY on discovery presence + activity recency + governance status. Finance evidence is retained as context/annotation only (reason codes like `HAS_FINANCE`/`NO_FINANCE` for priority/scoring), but never affects the shadow True/False decision.

### Vendor Hypothesis (Inference Layer)

An inference layer generates a `vendor_hypothesis` (max 0.9 confidence) from domain patterns for discovery-only assets, based on curated domain-to-vendor mappings. This hypothesis is non-decisionable metadata and does not affect admission, classification, findings, or policy logic.

### API Structure

A FastAPI application exposes endpoints for triggering runs (`/api/runs/from-farm`), retrieving run details, assets, and findings, and debug/reconciliation endpoints.

### Finance Admission Policy

Finance evidence requires **recurring spend** to qualify for admission:
- Contracts must have `is_recurring=true` and `amount > 0`
- Transactions must have `is_recurring=true` and `amount > 0`

One-time purchases and expense reimbursements are not actionable shadow IT and are excluded from finance-based admission.

### AOD Actual Results Emitter

AOD publishes its structured "actual" output (`shadow_actual`, `zombie_actual`, `admission_actual`, `actual_reason_codes`) to Farm for reconciliation. AOD outputs canonical reason codes (e.g., `HAS_IDP`, `NO_CMDB`) for all assets, ensuring no blank reason codes.

### Domain-Keyed Asset Aggregation

Assets are aggregated using a domain-keyed approach. If evidence contains a registered domain, that domain becomes the `asset_key`. This ensures reconciliation accuracy by prioritizing domains from evidence, vendor lookups, and normalized names. `is_shadow`/`is_zombie` use OR semantics, and `reason_codes` are a union of all variants (with contradictory codes deduplicated - HAS_* takes precedence over NO_*).

**Domain-First Key Normalization (Dec 2025):** Entities are keyed by their domain when available, not by name. This ensures proper aggregation of observations referring to the same service. If an observation name looks like a domain (e.g., "slack.com"), the domain is extracted from the name. If an entity is first created from non-domain evidence (e.g., "Slack" from IdP) and later receives domain evidence (e.g., "slack.com" from discovery), the entity is upgraded and re-keyed under the domain-based key with all observations merged. Base name matching allows "slack" to merge with "slack.com" when domain evidence arrives.

**Registered Domain Extraction (Dec 2025):** Asset keys are now normalized to their registered domain (eTLD+1) when evidence contains subdomains. For example, `images75.edge.com` → `edge.com`, `app.slack.com` → `slack.com`. This prevents KEY_NORMALIZATION_MISMATCH errors where Farm expects the registered domain but AOD was emitting the full subdomain. The `_extract_registered_domain()` function in `aod_agent_reconcile.py` now uses `extract_registered_domain()` from `vendor_inference.py` to properly extract registered domains from evidence.

**Domain Evidence Priority (Dec 2025):** Domain evidence (from identifiers.domains or domain-like asset names) ALWAYS takes priority over vendor inference. This prevents vendor lookups from overriding actual domain names. For example, an asset named `slack-hq.com` with `vendor=Slack` will be keyed as `slack-hq.com`, not `slack.com`. Vendor-to-domain lookup only applies when there is NO domain evidence. This preserves typosquat domains (`s1ack.com`, `g00gle.com`) and vendor variant domains (`sfdc.io`, `slackapp.com`) as separate assets.

### Reconciliation Eligibility Modes

Reconciliation eligibility is mode-based:
- **Sprawl mode** (default): Only external services (domains, known SaaS) are eligible for shadow/zombie classification. Internal identifiers (elasticsearchlogs, postgresmain) are excluded to prevent false positives.
- **Infra mode**: All assets are eligible, including internal identifiers. Use for infrastructure discovery reconciliation.

Mode can be specified via the `/runs/resync` endpoint: `{"run_id": "...", "mode": "infra"}`. Initial run creation uses sprawl mode by default.

### CMDB Correlation

CMDB correlation uses multiple matching strategies (in order):
1. **Domain matching** - Direct domain lookup in CMDB
2. **Canonical name matching** - Exact normalized name match with vendor validation
3. **Fuzzy matching** - Levenshtein distance for typos (ratio ≤ 0.20)
4. **Contains matching** - Substring matching with KNOWN_DISTINCT_PRODUCTS blocklist
5. **Name contains domain token** - CI name contains domain base token (≥6 chars)
6. **Vendor matching** - Entity vendor → CMDB vendor product index
7. **Domain-to-vendor matching** - Entity domain → DOMAIN_TO_VENDOR → CMDB vendor
8. **Vendor fallback** - Vendor-only match (loose governance)

**Name Contains Domain Token (Dec 2025):** Extracts base token from entity domain (e.g., `pagerduty.com` → `pagerduty`, `service-now.com` → `servicenow`) and matches if any CI name contains that token. Token must be ≥6 characters to prevent short-token false positives. Match method: `name_contains_domain_token`.

**Fuzzy Matching Ratio Gate (Dec 2025):** Edit-distance fuzzy matching uses a relative threshold: `distance/max_len ≤ 0.20`. This prevents short-token collisions (miro↔jira at 2/4=0.50, loom↔zoom at 1/4=0.25) while preserving legitimate longer fuzzy matches where 1-2 char typos are proportionally smaller.

**Vendor Validation (Dec 2025):** Canonical name matches against CMDB are validated using entity domain → DOMAIN_TO_VENDOR or entity name → VENDOR_TO_DOMAIN lookups to ensure the matched CMDB record's vendor matches the expected vendor for the entity.

**Domain Matching via external_ref (Dec 2025):** CMDB records with `external_ref` containing URLs have their domain extracted and indexed. Correlation now uses multi-signal matching: entity name → entity domain → vendor fallback.

**Vendor Fallback Matching (Dec 2025):** When name and domain matching fail, vendor fallback allows matching based on vendor alone. If `normalize(entity.vendor) == normalize(CI.vendor)`, the asset is considered governed (HAS_CMDB=True). This applies to both CMDB and IdP correlation.

**Governance Reason Codes (Dec 2025):** HAS_CMDB and HAS_IDP are now based on lens_status (raw matching) rather than lens_coverage (admission criteria). This ensures that any CMDB or IdP match counts as "governed" regardless of whether admission criteria like ci_type/lifecycle or has_sso/has_scim are met.

For detailed discovery logic documentation, see [DISCOVERY_LOGIC.md](./DISCOVERY_LOGIC.md).

### Infrastructure Domain Exclusion

Infrastructure domains (redis.io, postgresql.org, docker.com, kubernetes.io, etc.) are excluded from shadow/zombie classification. These represent internal infrastructure components that should not be flagged as shadow IT. The blocklist is maintained in `aod_agent_reconcile.py` as `INFRASTRUCTURE_DOMAINS`.

### LLM Fringe Resolution (Dec 2025)

For ambiguous assets where deterministic matching fails, an LLM-based fringe resolver provides classification assistance:

- **Trigger Conditions**: asset_type unknown, governance gap (NO_CMDB AND NO_IDP), or vendor ambiguous
- **Architecture**: Gemini-first with OpenAI fallback, 0.80 confidence threshold
- **Fact Store**: LLM facts are persisted in `llm_facts` table by (tenant_id, entity_key) for reuse across runs
- **INFRA_TECH Exclusion**: Assets classified as INFRA_TECH with high confidence (≥0.80) are excluded from shadow/zombie classification
- **Explainability**: LLMMetadata on Asset includes llm_used, llm_confidence, llm_reason, llm_asset_type, llm_canonical_vendor, llm_provider, llm_model_id, fact_id, exclusion_reason, and match methods

The LLM can provide CMDB/IdP matches via cmdb_ci_id/idp_object_id fields, creating an "llm_adjudicated" match method that promotes assets to governed status.

### Explain Non-Flag Endpoint

A `POST /api/reconcile/explain-nonflag` endpoint allows Farm to query why specific assets are NOT flagged as shadow/zombie, providing detailed reasons and decisions.

### Run Status Semantics

Runs return explicit statuses: `UPSTREAM_ERROR`, `INVALID_SNAPSHOT`, `INVALID_INPUT_CONTRACT`, `COMPLETED_NO_ASSETS`, `COMPLETED_WITH_RESULTS`.

### Database Design

PostgreSQL is used for persistence, configured via `SUPABASE_DB_URL` or `DATABASE_URL`. It includes tables for `runs`, `assets`, `findings`, `artifacts`, `observation_samples`, `ambiguous_matches`, and `rejections`. IDs are deterministic and run-scoped.

### Frontend

A single-page application using AutonomOS color palette and Quicksand font, providing a dropdown snapshot picker and drillable KPI cards.

## External Dependencies

-   **AOS Farm**: Upstream evidence source, providing snapshots via HTTP (`FARM_URL`) and receiving reconciliation results. AOD uses `farm_adapter.py` to normalize Farm's schema.
-   **FastAPI**: Python web framework for API development.
-   **Pydantic v2**: Data validation and serialization.
-   **asyncpg**: Asynchronous PostgreSQL database driver.
-   **httpx**: Asynchronous HTTP client for Farm communication.
-   **PostgreSQL**: Primary database for persistence.