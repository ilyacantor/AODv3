# AOD Discover — Executive Summary

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

An entity must pass ALL gates to become a **Cataloged Asset**:

| Gate | Rule |
|------|------|
| **GATE 0** | Valid public TLD (rejects `auth-service`, `token865`) |
| **GATE 1** | Not infrastructure domain (rejects `redis.com`, `postgresql.org`) |
| **GATE 2** | Evidence threshold: IdP/CMDB match OR Cloud match OR Finance (≥$200/mo recurring) OR Discovery with **≥2 distinct planes** |

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

## FINDINGS (Many-to-One)

Findings are **issues detected about admitted assets**. One asset can trigger multiple findings:

| Finding Type | Category | Trigger |
|--------------|----------|---------|
| `identity_gap` | Security Risk | Admitted via cloud/finance but no IdP |
| `finance_gap` | Security Risk | ≥$200/mo recurring spend, ungoverned |
| `data_conflict` | Security Risk | Conflicting values across planes (owner, env, etc.) |
| `cmdb_gap` | Governance | Has IdP/Finance but missing from CMDB |
| `governance_gap` | Governance | No owner or system records |
| `duplication_risk` | Governance | Multiple entities match same plane record |

---

## TRIAGE

Triage aggregates **everything needing human review**:

| Item Type | Source | Count Relationship |
|-----------|--------|-------------------|
| Findings | `generate_findings()` | Many per asset possible |
| Shadow Assets | `classify_shadow()` | 1 per shadow asset |
| Zombie Assets | `classify_zombie()` | 1 per zombie asset |

### Why item count > asset count?

- 1 asset can generate 5+ findings (identity + cmdb + data_conflict × N fields)
- Shadow/Zombie classifications add more items
- Each item → exactly 1 tier (mutually exclusive tiers)
- Same asset → can appear multiple times as different items

### Tier Prioritization

| Tier | Contains |
|------|----------|
| **Tier 1** | P0/P1 findings, identity_gap, finance_gap, financially-backed shadow |
| **Tier 2** | Data conflicts, ambiguous lens status |
| **Tier 3** | Everything else (backlog) |

---

## KEY DISTINCTIONS

| Concept | Unit | Can Repeat? |
|---------|------|-------------|
| Cataloged Asset | Unique admitted entity | No — 42 means 42 unique assets |
| Finding | Issue about an asset | Yes — 1 asset can have many findings |
| Triage Item | Finding OR shadow OR zombie | Yes — 1 asset can appear as multiple items |
| Classification | Shadow OR Zombie | No — each asset is one or neither |
