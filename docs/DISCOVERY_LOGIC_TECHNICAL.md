# AOD Discovery Logic — Technical Reference

> **What this document covers:** The nuts and bolts of how AOD matches and correlates data. It explains how entities are normalized (domain-first keying), the multi-pass matching strategies for CMDB and IdP correlation (domain match, fuzzy match, vendor fallback, etc.), how governance is determined, and the reason codes that explain each decision. Use this when you need to understand exactly how a match was made or debug correlation issues.

---

This document details the discovery and correlation logic used by AOD Fresh to identify, match, and classify enterprise assets.

## Table of Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Entity Normalization](#entity-normalization)
3. [CMDB Correlation](#cmdb-correlation)
4. [IdP Correlation](#idp-correlation)
5. [Governance Determination](#governance-determination)
6. [Shadow/Zombie Classification](#shadowzombie-classification)
7. [Infrastructure Exclusions](#infrastructure-exclusions)
8. [Reason Codes](#reason-codes)

---

## Pipeline Overview

AOD Fresh processes evidence through a 7-stage sequential pipeline:

```
Snapshot → Validate → Normalize → Index → Correlate → Admit → Artifacts → Findings
```

| Stage | File | Purpose |
|-------|------|---------|
| 1 | `validate_snapshot.py` | Schema validation, banned field rejection |
| 2 | `normalize_observations.py` | Normalize names/domains, derive candidate entities |
| 3 | `build_plane_indexes.py` | Create indexes for efficient correlation |
| 4 | `correlate_entities.py` | Multi-pass correlation with disambiguation |
| 5 | `admission.py` | Apply admission criteria to determine assets |
| 6 | `artifact_handler.py` | Identify and record artifacts (non-assets) |
| 7 | `findings_engine.py` | Generate deterministic findings |

---

## Entity Normalization

### Domain-First Keying

Entities are keyed by their **domain** when available, not by name. This ensures proper aggregation of observations referring to the same service.

**Key Rules:**
- If an entity has a domain, use the domain as the canonical key
- Name variants ("Slack", "Slack App") merge into domain key ("slack.com")
- If a name looks like a domain (e.g., "slack.com"), extract the domain from it

**Merge Behavior:**
```
Observation 1: name="Slack" (no domain) → key: "slack" (name-based)
Observation 2: name="slack.com" (domain detected) → upgrades to key: "slack.com"
Observation 3: uri="https://slack.com/app" → merges into "slack.com"

Result: Single entity keyed as "slack.com" with 3 observations
```

**Base Name Matching:**
When domain evidence arrives, the system checks if the domain's base name matches an existing name-only entity:
- `slack.com` → base name `slack` → matches existing `slack` entity → merges

---

## CMDB Correlation

CMDB correlation uses a **multi-pass matching strategy** executed in order. The first successful match wins.

### Matching Methods (in order)

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

### Method Details

#### 1. Domain Match
```python
plane_index.by_domain.get(entity.domain)
```
Direct domain lookup. Fastest and most accurate.

#### 2. Canonical Name Match
```python
plane_index.by_canonical_name.get(entity.canonical_name)
```
Exact normalized name match. Includes vendor validation when `use_vendor=True`.

#### 3. Fuzzy Match
```python
levenshtein_distance(entity.canonical_name, ci_name) / max_len <= 0.20
```
Allows 1-2 character typos in longer names. Short tokens (< 4 chars) are excluded.

**Ratio Gate:** Prevents false positives like `miro` ↔ `jira` (distance 2, ratio 0.50 > 0.20).

#### 4. Contains Match
```python
entity.canonical_name in ci_name or ci_name in entity.canonical_name
```
Substring matching with `KNOWN_DISTINCT_PRODUCTS` blocklist to prevent:
- "box" matching "dropbox"
- "hub" matching "github" or "hubspot"

#### 5. Name Contains Domain Token (NEW - Dec 2025)
```python
domain_token = extract_base_token(entity.domain)  # "pagerduty.com" → "pagerduty"
domain_token in ci_canonical_name  # "pagerduty" in "pagerduty legacy"
```
**Requirements:**
- Domain token must be ≥ 6 characters (prevents short token false positives)
- Hyphens/underscores are stripped (`service-now.com` → `servicenow`)

**Use Case:** Matches CIs with different names like "PagerDuty (Legacy)" to domain `pagerduty.com`.

#### 6. Vendor Match
```python
entity.vendor → plane_index.by_vendor_product
```
Requires name similarity between entity and matched CI.

#### 7. Domain-to-Vendor Match
```python
DOMAIN_TO_VENDOR[entity.domain] → vendor → plane_index.by_vendor_product
```
Uses curated domain-to-vendor mappings (e.g., `trello.com` → `Atlassian`).

#### 8. Vendor Fallback
```python
entity.vendor → plane_index.by_vendor_product (any match)
```
Loose matching: any CI with matching vendor counts as governed.

### Disambiguation

When multiple CIs match, disambiguation logic resolves using evidence from CI fields:

| Code | Resolution | Evidence |
|------|------------|----------|
| `MULTI_ENV` | Pick production | `environment` field differs |
| `LEGACY` | Pick active | `status`, `is_deprecated`, `lifecycle_state` |
| `DUPLICATE` | Pick first | Identical key fields |
| `PARENT_VENDOR` | Reject | Vendor-only match, no product match |
| `UNRESOLVED` | Remain ambiguous | No field evidence to disambiguate |

---

## IdP Correlation

IdP correlation follows the same multi-pass strategy as CMDB with these indexes:
- `by_canonical_name`: Normalized IdP object names
- `by_domain`: IdP object domains (if available)
- `by_vendor_product`: IdP vendor index

**IdP Admission Criteria:**
- `has_sso=True` OR `has_scim=True`

---

## Governance Determination

**Governance = HAS_CMDB OR HAS_IDP**

Governance is based on **matching** (lens_status), not **admission criteria** (lens_coverage).

| Field | Definition |
|-------|------------|
| `lens_status` | Raw plane matching (any match = True) |
| `lens_coverage` | Admission criteria met (SSO/SCIM, ci_type/lifecycle) |

**Example:**
```
Entity: pagerduty.com
CMDB Match: CI "PagerDuty (Legacy)" with lifecycle="retired"

lens_status.cmdb = True (matched)
lens_coverage.cmdb = False (lifecycle not production)
HAS_CMDB = True (governance based on lens_status)
```

---

## Shadow/Zombie Classification

### Shadow Asset
```
is_shadow = Discovered + Active + Ungoverned
         = (HAS_DISCOVERY OR HAS_CLOUD) 
           AND RECENT_ACTIVITY 
           AND NOT (HAS_CMDB OR HAS_IDP)
```

### Zombie Asset
```
is_zombie = Governed + Inactive
          = (HAS_CMDB OR HAS_IDP)
            AND STALE_ACTIVITY
```

### Activity Window
- **Recent**: Last activity within 90 days
- **Stale**: No activity in 90+ days

### Finance Policy
Finance is **NOT** a gate for shadow classification:
- `HAS_FINANCE` / `NO_FINANCE` are annotation-only reason codes
- Finance evidence does not affect `is_shadow` True/False decision

---

## Infrastructure Exclusions

Infrastructure domains are excluded from shadow/zombie classification. These represent internal components, not shadow IT.

**Excluded Domains:**
```
postgresql.org, mysql.com, apache.org, redis.io, redis.com,
mongodb.com, mongodb.org, docker.com, kubernetes.io, nginx.org,
python.org, nodejs.org, golang.org, rust-lang.org, ruby-lang.org,
linux.org, gnu.org, elastic.co, kafka.apache.org, jenkins.io,
terraform.io, hashicorp.com, grafana.com, prometheus.io, ...
```

Full list maintained in `aod_agent_reconcile.py` as `INFRASTRUCTURE_DOMAINS`.

---

## Reason Codes

### Presence Codes
| Code | Meaning |
|------|---------|
| `HAS_DISCOVERY` | Has discovery plane evidence |
| `HAS_IDP` | Matched to IdP object |
| `HAS_CMDB` | Matched to CMDB CI |
| `HAS_CLOUD` | Has cloud plane evidence |
| `HAS_FINANCE` | Has finance plane evidence |

### Absence Codes
| Code | Meaning |
|------|---------|
| `NO_IDP` | No IdP match |
| `NO_CMDB` | No CMDB match |
| `NO_CLOUD` | No cloud evidence |
| `NO_FINANCE` | No finance evidence |

### Activity Codes
| Code | Meaning |
|------|---------|
| `RECENT_ACTIVITY` | Activity within 90 days |
| `STALE_ACTIVITY` | No activity in 90+ days |
| `NO_ACTIVITY_TIMESTAMPS` | No timestamp data available |

### Admission Codes
| Code | Meaning |
|------|---------|
| `ADMITTED_VIA_IDP` | Admitted due to IdP match with SSO/SCIM |
| `ADMITTED_VIA_CMDB` | Admitted due to CMDB match with valid ci_type/lifecycle |
| `ADMITTED_VIA_FINANCE` | Admitted due to recurring finance spend |
| `ADMITTED_VIA_CLOUD` | Admitted due to cloud resource match |

---

## Match Explainability

Each plane match includes explainability fields:

| Field | Description |
|-------|-------------|
| `match_method` | Method used (domain, canonical_name, fuzzy, contains, name_contains_domain_token, vendor, domain_vendor, vendor_fallback) |
| `match_key` | The key that matched (domain, name, vendor, token) |
| `ambiguity_code` | Disambiguation code if multiple matches |
| `disambiguation_detail` | Explanation of resolution |

---

## Known Issues (Current Status)

### 1. Admission Noise Floor Bug
**Problem:** `check_discovery_admission()` counts distinct **planes** instead of distinct **sources**.

**Impact:** Assets with multiple discovery sources (browser, proxy, dns) that all map to the `network` plane get rejected despite meeting the ≥2 sources policy.

**Example:**
```
asana.com: 3 sources (browser, proxy, dns) → all map to "network" plane
Result: len(planes) = 1 → REJECTED (should be ADMITTED with 3 sources)
```

**Fix:** Modify `check_discovery_admission()` to count distinct sources, not distinct planes.

### 2. Key Normalization Mismatch
**Problem:** Domain canonicalization upgrades keys (e.g., `app.asana.com` → `asana.com`) but Farm reconciliation expects original keys.

**Impact:** Reconciliation marks assets as KEY_NORMALIZATION_MISMATCH even when correctly admitted.

**Fix Options:**
1. Emit alias metadata so Farm treats canonicalized keys as same asset
2. Update reconciliation to use canonical keys

---

## Version History

| Date | Change |
|------|--------|
| Dec 2025 | Added `name_contains_domain_token` matching method |
| Dec 2025 | Domain-first key normalization for entity merging |
| Dec 2025 | Governance based on lens_status (matching) not lens_coverage (admission) |
| Dec 2025 | Vendor fallback matching for CMDB and IdP |
| Dec 2025 | Infrastructure domain exclusion list expanded |
| Dec 2025 | Fuzzy matching ratio gate (≤ 0.20) |
| Dec 2025 | Risk Routing: Toxic assets (ACTIVE + identity_gap) route to Yellow queue |
| Dec 2025 | Finance badge: High-value shadows sort first in Red queue |
