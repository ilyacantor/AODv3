# AOD Discover — Executive Summary

> **What this document covers:** A high-level overview of how AOD processes enterprise data. It explains the pipeline stages (from raw evidence to cataloged assets), the rules for admitting or rejecting entities, how assets get classified as Shadow or Zombie, and the Traffic Light system that controls which assets are trusted. Use this as your quick reference for understanding what AOD does and why.

---

## LIFECYCLE (Pipeline Flow)

```
Raw Evidence → Validate → Normalize → Correlate → Admit → Classify → Generate Findings
     ↓             ↓          ↓           ↓          ↓         ↓              ↓
  Snapshot     Schema OK   Iron Dome   Match to   Pass/Fail  Shadow/    Security Risks
  from Farm               (reject      planes    gates      Zombie      & Governance
                          hostnames)                                     Issues
```

### Lifecycle KPIs (Row 1)

| Metric | Definition |
|--------|------------|
| **Ingested** | Raw observations received from Farm |
| **Validated** | Passed schema + Iron Dome (valid domain, not internal hostname) |
| **Rejected** | Failed validation OR admission gates |
| **Cataloged** | Admitted to Asset Catalog (passed all gates) |

---

## ADMISSION GATES

An entity must pass ALL rejection gates, then satisfy at least ONE admission criterion:

### Rejection Gates (must pass all)

| Gate | Rule |
|------|------|
| **GATE 0** | Valid public TLD (rejects `auth-service`, `token865`) |
| **GATE 1** | Not corporate root domain (rejects marketing domains) |
| **GATE 2** | Not infrastructure domain (rejects `redis.com`, `postgresql.org`) |

### Admission Criteria (must satisfy at least one)

| Criterion | Rule |
|-----------|------|
| **IdP** | Any IdP match (SSO/SCIM/service principal preferred) |
| **CMDB** | Any CMDB match (app/service/database/infra in prod/staging preferred) |
| **Cloud** | Any cloud resource match |
| **Finance** | Any spend > $0 (recurring preferred) |
| **Discovery** | ≥2 distinct corroborating planes + activity within 90 days |

**Note:** Discovery corroboration planes are: network, endpoint, idp, cloud, discovery. Finance and CMDB do NOT count as discovery corroboration.

---

## CLASSIFICATIONS (Row 2)

Applied **after admission** to cataloged assets:

| Classification | Definition | Trigger |
|----------------|------------|---------|
| **Shadow** | Active but ungoverned | Has discovery/cloud activity + NO IdP + NO CMDB |
| **Zombie** | Governed but inactive | Has IdP or CMDB + NO activity in 90 days |
| **Security Risks** | Findings requiring action | Identity gaps, finance gaps, data conflicts |
| **Governance** | Hygiene issues | CMDB gaps, governance gaps, duplication risks |

**Important:** Shadow and Zombie are **mutually exclusive** — an asset cannot be both.

---

## TRAFFIC LIGHT PROVISIONING

The Traffic Light system controls which assets flow to DCL (Discovery Control Layer). It operates on a **fail-closed** principle with strict precedence.

### Provisioning Status

| Status | Color | Definition | DCL Flow |
|--------|-------|------------|----------|
| **ACTIVE** | 🟢 Green | Trusted (has IdP or CMDB governance) | ✅ Flows to DCL |
| **REVIEW** | 🟡 Amber | Needs cleanup (CMDB but stale activity >90 days) | ❌ Blocked |
| **QUARANTINE** | 🔴 Red | Shadow IT (Cloud/Finance/Discovery only, no governance) | ❌ Blocked |
| **IGNORED** | ⚫ Black | Hard rejection (invalid TLD, infrastructure domain) | ❌ Dropped |

### Precedence Order

```
STEP 0: Hard rejection → IGNORED (dropped, not saved)
    ↓ (passes rejection gates)
STEP 1: Has IdP OR CMDB → ACTIVE (Green Lane)
    ↓ (no IdP/CMDB)
STEP 2: Has CMDB + Stale Activity → REVIEW (Amber Lane)
    ↓ (no CMDB)
STEP 3: Cloud/Finance/Discovery only → QUARANTINE (Red Lane)
```

### Decision Logic

| Evidence | Activity | Status | Reason |
|----------|----------|--------|--------|
| IdP match | Any | ACTIVE | Trusted identity governance |
| CMDB match | Recent (<90d) | ACTIVE | Trusted system record |
| CMDB match | Stale (>90d) | REVIEW | Zombie candidate, needs cleanup |
| Cloud only | Any | QUARANTINE | No governance, shadow IT |
| Finance only | Any | QUARANTINE | No governance, shadow IT |
| Discovery only | 2+ planes | QUARANTINE | No governance, shadow IT |

### API Endpoints

| Endpoint | Returns | Use Case |
|----------|---------|----------|
| `GET /api/v1/catalog?run_id=X` | All assets | Full inventory view |
| `GET /api/v1/catalog?run_id=X&provisioning_status=active` | ACTIVE only | Filtered view |
| `GET /api/v1/catalog/dcl?run_id=X` | ACTIVE only | DCL export (guardrailed) |

**Key Principle:** The DCL endpoint is the guardrail that ensures only ACTIVE assets flow downstream. QUARANTINE assets are visible in triage but blocked from production provisioning.

---

## FINDINGS (Many-to-One)

Findings are **issues detected about admitted assets**. One asset can trigger multiple findings:

### Security Risks (headline KPIs)

| Finding Type | Category | Trigger |
|--------------|----------|---------|
| `identity_gap` | Identity & Access | Admitted via cloud/finance but no IdP |
| `finance_gap` | Shadow IT | ≥$200/mo recurring spend + ungoverned |
| `data_conflict` | Data Integrity | Conflicting values across planes (owner, env, etc.) |

### Governance (secondary KPIs)

| Finding Type | Category | Trigger |
|--------------|----------|---------|
| `cmdb_gap` | Visibility Gap | Has IdP/Finance but missing from CMDB |
| `governance_gap` | Governance Hygiene | No owner or system records |
| `duplication_risk` | Governance Hygiene | Multiple entities match same plane record |

---

## TRIAGE (Gatekeeper UI)

Triage uses a **three-section workflow** based on provisioning status and risk type:

### Section Structure

| Section | Color | Contains | Actions |
|---------|-------|----------|---------|
| **Firewall** | 🔴 Red | QUARANTINE shadow IT | Approve, Ban |
| **Risk** | 🟡 Yellow | REVIEW zombies + ACTIVE with identity_gap (toxic) | Deprovision, Sanction, Dismiss Risk |
| **Hygiene** | 🟢 Green | ACTIVE with other findings | Acknowledge, Assign Owner |

### Routing Logic

```
Asset Status + Finding Type → Section
─────────────────────────────────────────
QUARANTINE (shadow IT)          → Red (Firewall)
REVIEW (zombie)                 → Yellow (Risk)
ACTIVE + identity_gap (toxic)   → Yellow (Risk)
ACTIVE + other findings         → Green (Hygiene)
```

### Special Behaviors

- **High-Value Shadow**: QUARANTINE assets with FINANCE_GAP show ($) badge and sort to top of Red queue
- **Toxic Assets**: ACTIVE assets with identity_gap (trusted by CMDB but missing IdP) route to Yellow with "Dismiss Risk" option
- **Batch Operations**: Green section supports batch acknowledgment via checkboxes

---

## KEY DISTINCTIONS

| Concept | Unit | Can Repeat? |
|---------|------|-------------|
| Cataloged Asset | Unique admitted entity | No — 42 means 42 unique assets |
| Finding | Issue about an asset | Yes — 1 asset can have many findings |
| Triage Item | Finding OR shadow OR zombie | Yes — 1 asset can appear as multiple items |
| Classification | Shadow OR Zombie | No — each asset is one or neither |
