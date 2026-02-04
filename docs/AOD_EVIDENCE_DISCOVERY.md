# AOD Evidence Discovery — Master Reference

> **Version:** 2.0.0 (Feb 2026 Blueprint)  
> **Last Updated:** 2026-02-04  
> **Purpose:** This is the single authoritative source for AOD (AutonomOS Discover) evidence discovery logic. It consolidates pipeline flow, admission policy, classification, and the new 3-tier evidence-based fabric plane detection system.

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [End-to-End Pipeline](#2-end-to-end-pipeline)
3. [Evidence Planes & 3-Tier Evidence System](#3-evidence-planes--3-tier-evidence-system)
4. [Admission Gates & Rejection Rules](#4-admission-gates--rejection-rules)
5. [Correlation & Normalization](#5-correlation--normalization)
6. [Fabric Plane Detection & Routing](#6-fabric-plane-detection--routing)
7. [Classification & Traffic Lights](#7-classification--traffic-lights)
8. [Policy Switchboard Impacts](#8-policy-switchboard-impacts)
9. [Outputs, Artifacts & AAM Handoff](#9-outputs-artifacts--aam-handoff)
10. [Known Limitations & Debug Tips](#10-known-limitations--debug-tips)

---

## 1. Purpose & Scope

### What AOD Does

AOD (AutonomOS Discover) processes raw enterprise evidence from multiple observation planes to produce a verified Asset Catalog. It answers:

- **What SaaS/services exist?** — Discovery across 7 data planes
- **Which are governed?** — IdP/CMDB correlation
- **Which are shadow IT?** — Ungoverned but active assets
- **Which are zombies?** — Governed but inactive assets
- **How do they connect?** — Fabric plane routing (iPaaS, API Gateway, etc.)

### Scope of This Document

This document covers:
- The complete pipeline from raw evidence to cataloged assets
- The 3-tier evidence confidence system (Feb 2026 blueprint)
- Admission/rejection policy and key invariants
- Fabric plane detection with evidence-based routing
- Traffic light provisioning for DCL handoff

### Key Architectural Principles (Feb 2026)

| Principle | Description |
|-----------|-------------|
| **Evidence-Based Routing** | A pipe's fabric plane is determined by evidence of how AOD discovered the connection — NEVER by inferring from asset type |
| **3-Tier Confidence** | Tier 1 (0.95) direct crawl → Tier 2 (0.70-0.90) observation → Tier 3 (0.30-0.50) inference |
| **Multi-Plane Support** | One SOR can have multiple pipes through different fabric planes |
| **No Default to iPaaS** | Unknown assets get NO assignment, flagged for investigation |
| **Evidence Trail** | Every classification has attached evidence records |
| **Fabric Planes First** | Find control planes (MuleSoft, Kong, Snowflake) before individual endpoints |
| **Fail-Closed Traffic Lights** | Default is QUARANTINE — only explicitly trusted assets flow to DCL |

---

## 2. End-to-End Pipeline

### Pipeline Flow

```
Raw Evidence → Validate → Normalize → Correlate → Admit → Classify → Generate Findings → Handoff
     ↓             ↓          ↓           ↓          ↓         ↓            ↓              ↓
  Snapshot     Schema OK   Iron Dome   Match to   Pass/Fail  Shadow/    Security Risks   AAM/DCL
  from Farm               (reject      planes    gates      Zombie/     & Governance     Export
                          hostnames)             (5 gates)  Traffic     Issues
                                                            Light
```

### Pipeline Stages

| Stage | File | Purpose |
|-------|------|---------|
| 1. **Validate** | `validate_snapshot.py` | Schema validation, banned field rejection, Iron Dome filtering |
| 2. **Normalize** | `normalize_observations.py` | Normalize names/domains, derive candidate entities, domain-first keying |
| 3. **Index** | `build_plane_indexes.py` | Create indexes for efficient IdP/CMDB/Cloud/Finance correlation |
| 4. **Correlate** | `correlate_entities.py` | Multi-pass matching (domain → name → vendor) with disambiguation |
| 5. **Admit** | `admission.py` | Apply 5 admission gates, reject non-qualifying entities |
| 6. **Artifacts** | `artifact_handler.py` | Filter non-system objects (dashboards, reports) |
| 7. **Fabric Detect** | `fabric_detector.py` | Evidence-based fabric plane assignment with 3-tier confidence |
| 8. **Classify** | `derived_classifications.py` | Shadow/Zombie classification, Traffic Light provisioning |
| 9. **Findings** | `findings_engine.py` | Generate deterministic findings (identity_gap, cmdb_gap, etc.) |

### Lifecycle KPIs

| Metric | Definition |
|--------|------------|
| **Ingested** | Raw observations received from Farm snapshot |
| **Validated** | Passed schema + Iron Dome (valid domain, not internal hostname) |
| **Rejected** | Failed validation OR admission gates |
| **Cataloged** | Admitted to Asset Catalog (passed at least one admission gate) |

---

## 3. Evidence Planes & 3-Tier Evidence System

### Evidence Planes (7 Data Planes)

| Plane | Description | Example Evidence |
|-------|-------------|------------------|
| **Discovery** | DNS, proxy logs, browser, network scans | Domain visits, DNS queries, browser extensions |
| **IdP** | Identity Provider | SSO apps, SCIM provisioning, service principals |
| **CMDB** | Configuration Management Database | CI records, system-of-record entries |
| **Cloud** | Cloud resource inventory | AWS/Azure/GCP resources, SaaS integrations |
| **Endpoint** | Device/agent data | Installed software, device telemetry |
| **Network** | Traffic/topology | Flow logs, firewall rules, API traffic patterns |
| **Finance** | Spend/billing | Contracts, invoices, recurring transactions |

### 3-Tier Evidence Confidence System

**This is a key change from the legacy flat 0.70 confidence.** The new system uses tiered confidence based on evidence quality:

| Tier | Confidence Range | Source | Description |
|------|------------------|--------|-------------|
| **Tier 1** | 0.95 | Direct fabric plane catalog crawl | Authoritative — plane admin API confirms the connection |
| **Tier 2** | 0.70 - 0.90 | Observation plane signals | Network traffic, cloud inventory, finance records |
| **Tier 3** | 0.30 - 0.50 | Category-based inference | **DEMOTED** — last resort, explicitly flagged as hypothesis |

#### Tier 2 Confidence Breakdown

| Confidence | Signal Type |
|------------|-------------|
| 0.90 | Fabric plane itself found in cloud inventory |
| 0.85 | Clear traffic pattern or explicit dependency |
| 0.80 | OAuth grant or service account connection |
| 0.70 | Indirect signal, corroborating evidence |

#### Tier 3 Confidence Breakdown (Demoted)

| Confidence | Match Quality |
|------------|---------------|
| 0.50 | Strong category match with iPaaS present in environment |
| 0.40 | Moderate category match |
| 0.30 | Weak inference, flagged as hypothesis |

### Evidence Collection Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Evidence Collection (Phase 1)                     │
├─────────────────────────────────────────────────────────────────────┤
│  CloudEvidenceCollector     → Scans cloud inventory for plane refs  │
│  NetworkEvidenceCollector   → Analyzes traffic patterns/flows       │
│  FinanceEvidenceCollector   → Maps vendor spend to plane vendors    │
│  CMDBEvidenceCollector      → Extracts integration metadata         │
│  IdPEvidenceCollector       → Finds OAuth grants to plane vendors   │
├─────────────────────────────────────────────────────────────────────┤
│                 Output: EvidenceCollectionResult                     │
│  - routing_evidence: Dict[asset_key, RoutingEvidenceTable]          │
│  - fabric_plane_registry: FabricPlaneRegistry                       │
│  - shadow_plane_candidates: List[FabricPlane]                       │
│  - unattached_assets: List[str]                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### CMDB Fabric Routing Fields (Feb 2026)

CMDB Configuration Items can include explicit fabric plane routing declarations via two fields:

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `integrates_via` | string | `ipaas`, `api_gateway`, `event_bus`, `data_warehouse` | The fabric plane type this asset routes through |
| `fabric_vendor` | string | `workato`, `mulesoft`, `kong`, `snowflake`, etc. | The specific fabric plane vendor instance |

**Example CMDB CI with fabric routing:**
```json
{
  "ci_id": "ci-sf-001",
  "name": "Salesforce",
  "ci_type": "app",
  "integrates_via": "ipaas",
  "fabric_vendor": "workato"
}
```

**Evidence Generation:** When `integrates_via` is set, CMDBEvidenceCollector creates Tier 2 evidence (confidence=0.75) with signal_type `cmdb_integrates_via`.

**Data Quality Requirements for Farm:**
1. **Real enterprise apps MUST have `integrates_via` set.** Priority apps: Salesforce, Workday, BambooHR, Zendesk, NetSuite, ServiceNow, Jira, HubSpot, Datadog, GitHub, Slack, Okta
2. **`fabric_vendor` MUST match detected planes.** If snapshot detects Workato, Kong, Snowflake, Kafka as planes, CMDB `fabric_vendor` values must reference these — NOT planes that don't exist in the environment (e.g., Boomi, AWS API Gateway)
3. **Coverage target: 61-80% of CMDB CIs should have `integrates_via` set**

---

## 4. Admission Gates & Rejection Rules

### Rejection Gates (Must Pass ALL)

Entities must pass ALL rejection gates before admission evaluation:

| Gate | Rule | Examples Rejected |
|------|------|-------------------|
| **GATE 0: Valid TLD** | Must have valid public TLD | `auth-service`, `token865`, `localhost` |
| **GATE 1: Not Corporate Root** | Not vendor's main marketing website | `google.com`, `hubspot.com`, `servicenow.com` |
| **GATE 2: Not Infrastructure** | Not infrastructure technology domain | `redis.com`, `postgresql.org`, `kubernetes.io` |

### Admission Gates (Must Satisfy At Least ONE)

| Gate | Criteria | Purpose |
|------|----------|---------|
| **IdP Gate** | IdP match AND (`has_sso` OR `has_scim` OR `idp_type=service_principal`) | Identity-governed apps |
| **CMDB Gate** | CMDB match AND `ci_type` ∈ {app, service, database, infra} AND `lifecycle` ∈ {prod, staging} | System-of-record assets |
| **Cloud Gate** | Cloud match AND `resource_type` indicates real system/resource | Cloud-provisioned resources |
| **Finance Gate** | Finance match AND (contract exists OR recurring vendor spend ≥$200/mo) | Financially-backed services |
| **Discovery Gate** | ≥2 distinct discovery **sources** AND activity within 90 days | Shadow IT candidates |

**Important (Dec 2025 Fix):** Discovery admission gates on distinct **sources** (browser, proxy, dns = 3 sources), NOT distinct planes. Plane diversity is an annotation only, not a blocker.

### Key Invariants

| Invariant | Description |
|-----------|-------------|
| **Vendor governance alone NEVER admits** | Vendor match is metadata only, not an admission criterion |
| **Corporate roots ALWAYS rejected** | Regardless of other evidence |
| **vendor_hypothesis is NON-DECISIONABLE** | Used for display only, never for admission/classification |
| **Deterministic output** | Identical inputs always produce identical outputs |

### Admission Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMISSION DECISION TREE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Is domain a corporate root domain?                             │
│    YES → REJECT                                                  │
│    NO  ↓                                                         │
│                                                                  │
│  Is domain an infrastructure domain?                            │
│    YES → REJECT                                                  │
│    NO  ↓                                                         │
│                                                                  │
│  Does entity satisfy ANY gate?                                   │
│    • IdP: match + (SSO|SCIM|service_principal)                  │
│    • CMDB: match + valid ci_type + valid lifecycle              │
│    • Cloud: match + real resource_type                          │
│    • Finance: match + (contract|recurring spend ≥$200)          │
│    • Discovery: ≥2 sources + activity ≤90 days                  │
│                                                                  │
│    YES → ADMIT (Cataloged)                                       │
│    NO  → REJECT                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Correlation & Normalization

### Domain-First Keying

Entities are keyed by their **domain** when available, not by name. This ensures proper aggregation of observations referring to the same service.

**Key Rules:**
- If an entity has a domain, use the domain as the canonical key
- Name variants ("Slack", "Slack App") merge into domain key ("slack.com")
- If a name looks like a domain (e.g., "slack.com"), extract the domain from it

**Merge Behavior:**
```
Observation 1: name="Slack" (no domain)     → key: "slack" (name-based)
Observation 2: name="slack.com" (detected)  → upgrades to key: "slack.com"
Observation 3: uri="https://slack.com/app"  → merges into "slack.com"

Result: Single entity keyed as "slack.com" with 3 observations
```

### Multi-Pass CMDB Correlation

CMDB correlation uses a **multi-pass matching strategy** executed in order. First successful match wins:

| # | Method | Match Key | Requirements |
|---|--------|-----------|--------------|
| 1 | **Domain** | `entity.domain` | CMDB CI has matching `domain` field |
| 2 | **Canonical Name** | `entity.canonical_name` | Exact normalized name match + vendor validation |
| 3 | **Fuzzy** | Levenshtein distance | Edit distance ratio ≤ 0.20 |
| 4 | **Contains** | Substring | Entity name in CI name or vice versa |
| 5 | **Name Contains Domain Token** | Domain base token | CI name contains domain token (≥6 chars) |
| 6 | **Vendor** | `entity.vendor` | Entity vendor matches CI vendor + name similarity |
| 7 | **Domain-to-Vendor** | DOMAIN_TO_VENDOR lookup | Entity domain → vendor → CI vendor + name similarity |
| 8 | **Vendor Fallback** | `entity.vendor` | Vendor-only match (loose, intentionally) |

### Multi-Pass IdP Correlation

IdP correlation follows the same strategy with these indexes:
- `by_canonical_name`: Normalized IdP object names
- `by_domain`: IdP object domains (if available)
- `by_vendor_product`: IdP vendor index

**IdP Admission Criteria:** `has_sso=True` OR `has_scim=True` OR `idp_type=service_principal`

### Disambiguation Codes

When multiple records match, disambiguation logic resolves using evidence:

| Code | Resolution | Evidence |
|------|------------|----------|
| `MULTI_ENV` | Pick production | `environment` field differs |
| `LEGACY` | Pick active | `status`, `is_deprecated`, `lifecycle_state` |
| `DUPLICATE` | Pick first | Identical key fields |
| `PARENT_VENDOR` | Reject | Vendor-only match, no product match |
| `UNRESOLVED` | Remain ambiguous | No field evidence to disambiguate |

---

## 6. Fabric Plane Detection & Routing

### Strategic Priority: Find Control Planes FIRST

> "Finding 500 APIs is useless if they're all managed by one MuleSoft instance."

The fabric detection strategy prioritizes discovering control planes (MuleSoft, Kong, Snowflake, etc.) before individual endpoint assets. This provides:
- Accurate routing evidence for all managed assets
- Shadow plane detection (fabric planes not in official inventory)
- Multi-plane support for assets with multiple routing paths

### Fabric Plane Types

| Plane Type | Description | Example Vendors |
|------------|-------------|-----------------|
| **iPaaS** | Integration Platform as a Service | MuleSoft, Workato, Boomi, Tray, Zapier |
| **API Gateway** | API management and gateway | Kong, Apigee, AWS API Gateway, Azure API Mgmt |
| **Event Bus** | Event streaming and messaging | Kafka, Confluent, EventBridge, Kinesis |
| **Data Warehouse** | Data warehouse and analytics | Snowflake, BigQuery, Redshift, Databricks |

### Three-Phase Fabric Detection

```
┌─────────────────────────────────────────────────────────────────────┐
│              PHASE 1: Observation Plane Harvest                      │
│  Extract fabric plane signals from Cloud, Network, Finance, etc.    │
│  Output: EvidenceCollectionResult with routing evidence             │
├─────────────────────────────────────────────────────────────────────┤
│              PHASE 2: Direct Plane Crawl (Sprint 2)                  │
│  Query plane admin APIs: Kong Admin, Workato Recipes, Snowflake    │
│  Output: Tier 1 authoritative evidence (0.95 confidence)            │
├─────────────────────────────────────────────────────────────────────┤
│              PHASE 3: Reconciliation                                 │
│  Cross-reference evidence, compute composite confidence             │
│  Detect contradictions, flag multi-plane assets                     │
│  Output: Pipes with evidence trails, FabricPlaneTag assignments     │
└─────────────────────────────────────────────────────────────────────┘
```

### Pipes Model

A **Pipe** represents a connection between a source system (SOR) and a fabric plane with attached evidence:

```
Pipe {
    pipe_id: "pipe_abc123"
    name: "Workato Instance 1 → Salesforce"
    source_system: "salesforce.com"
    fabric_plane: FabricPlaneType.IPAAS
    fabric_plane_instance: "Workato Production"
    modality: ConnectivityModality.CONTROL_PLANE
    classification_method: ClassificationMethod.OBSERVED
    classification_evidence: [FabricRoutingEvidence...]
    classification_confidence: 0.85
    evidence_tier: EvidenceTier.TIER_2_OBSERVED
    has_contradictions: false
}
```

### Multi-Plane Support

**One SOR can have multiple pipes through different planes:**

```
salesforce.com:
  ├─ Pipe 1: MuleSoft (iPaaS) → confidence 0.85
  ├─ Pipe 2: Snowflake (Data Warehouse) → confidence 0.80
  └─ Pipe 3: Kong (API Gateway) → confidence 0.70
```

### Composite Confidence Scoring

| Evidence Combination | Composite Confidence |
|---------------------|---------------------|
| Single Tier 1 evidence (direct crawl) | 0.95 |
| Multiple Tier 2 (2+ observation planes agree) | 0.85 |
| Single Tier 2 evidence | 0.70-0.75 |
| Tier 3 only (category inference) | 0.30-0.50 |
| No evidence | **NO assignment** (don't guess) |

### Category-to-Plane Inference (Tier 3 — DEMOTED)

Only used when NO observation plane or direct crawl evidence exists:

| Category Keywords | Inferred Plane | Confidence |
|-------------------|---------------|------------|
| crm, erp, finance, hcm, hris, itsm, marketing, sales | iPaaS | 0.35-0.50 |
| api, gateway, rest, graphql | API Gateway | 0.35-0.50 |
| data, analytics, bi, reporting, warehouse | Data Warehouse | 0.35-0.50 |
| messaging, stream, queue, events | Event Bus | 0.35-0.50 |

**CRITICAL:** Unknown assets with no category match get **NO assignment**. The system no longer defaults to iPaaS.

---

## 7. Classification & Traffic Lights

### Shadow vs Zombie Classification

Applied **after admission** to cataloged assets:

| Classification | Definition | Trigger |
|----------------|------------|---------|
| **Shadow** | Active but ungoverned | Has discovery/cloud activity + NO IdP + NO CMDB |
| **Zombie** | Governed but inactive | Has IdP or CMDB + NO activity in 90 days |

**Important:** Shadow and Zombie are **mutually exclusive** — an asset cannot be both.

### Traffic Light Provisioning System

The Traffic Light system controls which assets flow to DCL (Discovery Control Layer). It operates on a **fail-closed** principle.

| Status | Color | Definition | DCL Flow |
|--------|-------|------------|----------|
| **ACTIVE** | 🟢 Green | Trusted (has IdP or CMDB governance) | ✅ Flows to DCL |
| **REVIEW** | 🟡 Amber | Needs cleanup (CMDB but stale activity >90 days) | ❌ Blocked |
| **QUARANTINE** | 🔴 Red | Shadow IT (Cloud/Finance/Discovery only, no governance) | ❌ Blocked |
| **BLOCKED** | ⚫ Black | User rejected via BAN action | ❌ Permanently blocked |
| **RETIRED** | ⬛ Gray | User deprovisioned | ❌ Removed from active use |
| **IGNORED** | ⚫ Black | Hard rejection (invalid TLD, infrastructure domain) | ❌ Dropped |

### Traffic Light Precedence

```
STEP 0: Hard rejection → IGNORED (dropped, not saved)
    ↓ (passes rejection gates)
STEP 1: Has IdP OR CMDB → ACTIVE (Green Lane)
    ↓ (no IdP/CMDB)
STEP 2: Has CMDB + Stale Activity → REVIEW (Amber Lane)
    ↓ (no CMDB)
STEP 3: Cloud/Finance/Discovery only → QUARANTINE (Red Lane)
```

### Traffic Light Decision Matrix

| Evidence | Activity | Status | Reason |
|----------|----------|--------|--------|
| IdP match | Any | ACTIVE | Trusted identity governance |
| CMDB match | Recent (<90d) | ACTIVE | Trusted system record |
| CMDB match | Stale (>90d) | REVIEW | Zombie candidate, needs cleanup |
| Cloud only | Any | QUARANTINE | No governance, shadow IT |
| Finance only | Any | QUARANTINE | No governance, shadow IT |
| Discovery only | 2+ sources | QUARANTINE | No governance, shadow IT |

---

## 8. Policy Switchboard Impacts

### Key Policy Settings Affecting Discovery

| Setting | Default | Impact on Discovery |
|---------|---------|---------------------|
| `discovery_activity_window_days` | 90 | Days to consider for activity status |
| `zombie_window_days` | 90 | Days of inactivity for zombie classification |
| `minimum_spend` | $200 | Finance gate threshold for admission |
| `noise_floor` | 1 | Minimum discovery sources for admission |
| `require_sso_for_idp` | true | Require SSO/SCIM for IdP governance |
| `require_valid_ci_type` | true | Require valid CI type for CMDB governance |
| `require_corroboration` | true | Require 2+ sources for discovery-only admission |
| `enable_vendor_propagation` | true | Allow governance inheritance from vendor siblings |

### Admission Gate Switches

| Switch | When TRUE | When FALSE |
|--------|-----------|------------|
| `require_sso_for_idp` | Must have SSO/SCIM/service_principal | Any IdP presence counts |
| `require_valid_ci_type` | CI type must be app/service/database/infra | Any CMDB presence counts |
| `require_valid_lifecycle` | Lifecycle must be prod/staging/live/active | Any lifecycle accepted |
| `allow_finance_only_admission` | Finance alone can admit | Finance requires corroboration |
| `finance_requires_discovery` | Finance needs discovery evidence | Finance can admit without discovery |

### Exclusion Lists

| List | Contents |
|------|----------|
| **Banned Domains** | googleapis.com, microsoft.com, amazonaws.com, etc. |
| **Infrastructure Domains** | redis.io, postgresql.org, kubernetes.io, etc. |
| **Corporate Root Domains** | Customer marketing domains (operator-configured) |

---

## 9. Outputs, Artifacts & AAM Handoff

### Output Artifacts

| Artifact | Description |
|----------|-------------|
| **Asset Catalog** | All admitted assets with classifications and evidence |
| **Rejection Log** | All rejected entities with reason codes |
| **Findings** | Security risks and governance issues |
| **Fabric Plane Registry** | Detected fabric planes and shadow candidates |
| **Pipes** | SOR-to-plane connections with evidence trails |
| **Run Log** | Pipeline execution metadata and timings |

### Findings Types

#### Security Risks (Headline KPIs)

| Finding | Trigger |
|---------|---------|
| `IDENTITY_GAP` | Admitted via Cloud/Finance but no IdP |
| `FINANCE_GAP` | ≥$200/mo recurring spend + ungoverned |
| `DATA_CONFLICT` | Conflicting values across planes |

#### Governance (Secondary KPIs)

| Finding | Trigger |
|---------|---------|
| `CMDB_GAP` | Has IdP/Finance but missing from CMDB |
| `GOVERNANCE_GAP` | No owner or system records |
| `DUPLICATION_RISK` | Multiple entities match same plane record |

### AAM Handoff

Assets flow to AAM (Asset & Access Management) based on Traffic Light status:

| Status | AAM Action |
|--------|------------|
| **ACTIVE** | Auto-provisioned to DCL |
| **REVIEW** | Queued for zombie cleanup |
| **QUARANTINE** | Queued for triage (approve/ban) |
| **BLOCKED** | Excluded from AAM |
| **RETIRED** | Archived in AAM |

### API Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/v1/catalog?run_id=X` | All assets |
| `GET /api/v1/catalog?run_id=X&provisioning_status=active` | ACTIVE only |
| `GET /api/v1/catalog/dcl?run_id=X` | ACTIVE only (DCL export) |
| `GET /api/v1/fabric/planes?run_id=X` | Fabric plane registry |
| `GET /api/v1/fabric/pipes?run_id=X` | All pipes with evidence |

---

## 10. Known Limitations & Debug Tips

### Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **Key Normalization Mismatch** | Domain canonicalization upgrades keys (app.asana.com → asana.com) but Farm may expect original keys | Use alias metadata for reconciliation |
| **Tier 3 Inference Quality** | Category-based inference is low confidence | Prioritize direct crawl and observation plane evidence |
| **OAuth Scope Mapping** | Limited visibility into OAuth grant scopes | Requires IdP-specific integration |
| **Vendor Fallback False Positives** | Loose vendor matching can match wrong products | Review PARENT_VENDOR disambiguation codes |

### Debug Tips

#### Tracing Admission Decisions

```bash
# Trace why an entity was admitted/rejected
GET /api/v1/debug/trace?entity=salesforce.com&run_id=X
```

Check for:
- `admission_reason`: Which gate(s) passed
- `rejection_reason`: Why entity was rejected
- `lens_status`: Raw plane matching results
- `lens_coverage`: Admission criteria met per plane

#### Debugging Fabric Plane Classification

```bash
# View evidence for an asset's fabric classification
GET /api/v1/fabric/evidence?asset_id=X
```

Check for:
- `evidence_tier`: Which tier provided the classification
- `classification_evidence`: Raw evidence records
- `has_contradictions`: Whether sources disagree
- `classification_confidence`: Composite confidence score

#### Common Debug Scenarios

| Symptom | Likely Cause | Debug Steps |
|---------|--------------|-------------|
| Asset rejected despite IdP match | `require_sso_for_idp=true` and no SSO | Check IdP record for `has_sso`, `has_scim` |
| Shadow asset not marked | Has CMDB match | Check `lens_status.cmdb` — might be retired CI |
| Wrong fabric plane | Tier 3 inference | Check for observation plane evidence |
| No fabric assignment | No evidence, unknown category | Expected behavior — requires manual review |
| Duplicate findings | Multiple entities match same CI | Check disambiguation codes |

#### Reason Codes Reference

| Code Type | Examples |
|-----------|----------|
| **Presence** | `HAS_IDP`, `HAS_CMDB`, `HAS_CLOUD`, `HAS_FINANCE`, `HAS_DISCOVERY` |
| **Absence** | `NO_IDP`, `NO_CMDB`, `NO_CLOUD`, `NO_FINANCE` |
| **Activity** | `RECENT_ACTIVITY`, `STALE_ACTIVITY`, `NO_ACTIVITY_TIMESTAMPS` |
| **Admission** | `ADMITTED_VIA_IDP`, `ADMITTED_VIA_CMDB`, `ADMITTED_VIA_FINANCE`, `ADMITTED_VIA_CLOUD` |
| **Discovery Source** | `DISCOVERY_SOURCE_COUNT_GE_2`, `DISCOVERY_SOURCE_COUNT_LT_2` |
| **Plane Diversity** | `PLANE_DIVERSITY_GE_2`, `PLANE_DIVERSITY_LT_2` (annotation only) |

---

## Version History

| Date | Version | Change |
|------|---------|--------|
| Feb 2026 | 2.0.0 | 3-tier evidence system, multi-plane support, no default to iPaaS |
| Jan 2026 | 1.5.0 | Traffic light provisioning, fail-closed DCL handoff |
| Dec 2025 | 1.4.0 | Discovery gates on sources (not planes), name_contains_domain_token matching |
| Dec 2025 | 1.3.0 | Domain-first key normalization, vendor fallback matching |
| Dec 2025 | 1.2.0 | Fuzzy matching ratio gate (≤ 0.20), infrastructure exclusions |
| Dec 2025 | 1.1.0 | Risk routing: toxic assets route to Yellow queue |
| Nov 2025 | 1.0.0 | Initial discovery logic documentation |

---

## Related Documents

- `docs/AOD_DISCOVER_LOGIC.md` — Executive summary (high-level overview)
- `docs/DISCOVERY_LOGIC_TECHNICAL.md` — Correlation methods deep dive
- `docs/aod-admission-policy.md` — Full admission policy details
- `docs/POLICY_SWITCHES.md` — Policy switchboard reference
- `docs/OPERATING_GUIDE.md` — Operational procedures
