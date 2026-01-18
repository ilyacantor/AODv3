# AOD - Asset Ownership Discovery
## Product Specification for AutonomOS Platform

**Version:** 1.0  
**Module:** AOD (Asset Ownership Discovery)  
**Platform:** AutonomOS (AOS)  
**URL:** discover.autonomos.tech

---

## Executive Summary

AOD is the discovery and classification engine for the AutonomOS platform. It automatically identifies every SaaS application, cloud service, and software asset running in an enterprise environment—including those IT doesn't know about.

**The Problem:** The average enterprise uses 400+ SaaS applications. IT typically knows about 30% of them. The rest is Shadow IT (security risk) or Zombie SaaS (wasted spend).

**The Solution:** AOD ingests signals from across the enterprise, correlates them into a trusted asset inventory, and classifies each asset by governance status—preparing everything for automated connection via the AutonomOS platform.

---

## Value Proposition

| Stakeholder | Pain Point | AOD Value |
|-------------|------------|-----------|
| **CISO/Security** | Unknown apps = unknown attack surface | Discovers 100% of SaaS, flags ungoverned assets |
| **CFO/Finance** | Paying for unused licenses | Identifies zombie subscriptions, quantifies waste |
| **CIO/IT** | Spreadsheet-based asset management | Automated, continuous discovery with single pane of glass |
| **Procurement** | Duplicate tools across departments | Surfaces duplication risk, enables consolidation |

---

## Platform Position

AOD is the **entry point** to the AutonomOS platform:

```
┌─────────────────────────────────────────────────────────────────┐
│                        AutonomOS Platform                        │
├─────────┬─────────┬─────────┬──────────────────────────────────┤
│   AOD   │   AAM   │   DCL   │           Agents                 │
│Discover │ Connect │  Unify  │   FinOps · RevOps · SecOps       │
├─────────┴─────────┴─────────┴──────────────────────────────────┤
│  "What's    "Connect    "Normalize     "Take intelligent       │
│   running?"  to it"      the data"      action"                │
└─────────────────────────────────────────────────────────────────┘
```

| Layer | Component | Function |
|-------|-----------|----------|
| **Discover** | AOD | Find and classify everything |
| **Connect** | AAM (Adaptive API Mesh) | Establish connections, manage auth |
| **Unify** | DCL (Data Connectivity Layer) | Canonical ontology, entity resolution |
| **Act** | Agents | Domain-specific AI (FinOps, RevOps, etc.) |

---

## Core Capabilities

### 1. Multi-Source Discovery

AOD ingests signals from multiple enterprise data sources:

| Source Type | Examples | What It Reveals |
|-------------|----------|-----------------|
| **Browser/Endpoint** | Browser history, extensions | Apps employees actually use |
| **Network** | DNS logs, proxy logs, firewall | All traffic, including unmanaged devices |
| **Identity** | SSO logs, IdP records | Governed vs ungoverned access |
| **Finance** | Credit cards, expense reports, invoices | Spend without IT oversight |
| **Cloud** | AWS, Azure, GCP inventory | Infrastructure sprawl |
| **CMDB** | ServiceNow, asset registers | What IT thinks they manage |

### 2. Intelligent Correlation

Raw signals are noisy. AOD uses multi-signal correlation to build a trusted inventory:

- **Entity Resolution:** `zoom.us`, `zoomgov.com`, `zoom-meetings.net` → single Zoom asset
- **Vendor Mapping:** Associates domains with canonical vendor identities
- **Conflict Resolution:** Reconciles disagreeing data sources with confidence scoring
- **Deduplication:** Prevents the same asset from appearing multiple times

### 3. Governance Classification

Every asset is classified into one of three governance states:

| Status | Definition | Action Required |
|--------|------------|-----------------|
| **Governed** | Has IdP/SSO, in CMDB, or vendor-managed | Ready for AAM connection |
| **Shadow IT** | Active usage without governance controls | Security review needed |
| **Zombie** | Governed but no recent activity | Cost optimization opportunity |

### 4. Findings Generation

AOD produces actionable findings for each asset:

| Finding | Severity | Description |
|---------|----------|-------------|
| `identity_gap` | High | No SSO integration—security risk |
| `finance_gap` | High | Spend without budget owner—compliance risk |
| `data_conflict` | Medium | Sources disagree—manual review needed |
| `cmdb_gap` | Low | Not in asset register—hygiene issue |
| `duplication_risk` | Low | Possible redundant tool |

### 5. Triage Workflow

Prioritized work queue for IT/Security teams:

- **Red (Blocking):** Must resolve before connecting to platform
- **Yellow (Review):** Cost optimization opportunities
- **Green (Informational):** Hygiene improvements

---

## Technical Specifications

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         AOD Engine                            │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Ingestion   │   Pipeline   │   Catalog    │    Triage      │
│              │              │              │                │
│ • Fetch      │ • Validate   │ • Assets     │ • Prioritize   │
│ • Normalize  │ • Correlate  │ • Artifacts  │ • Assign       │
│ • Index      │ • Classify   │ • Findings   │ • Resolve      │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

### Pipeline Stages

| Stage | Function | Output |
|-------|----------|--------|
| **Validation** | Verify data integrity | Clean input |
| **Normalization** | Standardize domains, extract tokens | Canonical keys |
| **Indexing** | Build lookup structures | Fast correlation |
| **Correlation** | Match across IdP, CMDB, Finance | Linked records |
| **Admission** | Apply gates (spend threshold, corroboration) | Admitted assets |
| **Classification** | Determine governance status | Shadow/Zombie/Governed |
| **Findings** | Generate actionable items | Prioritized work |

### Policy Switchboard

Central configuration for all business rules:

| Category | Example Settings |
|----------|------------------|
| **Activity Windows** | 90-day discovery window, 90-day zombie threshold |
| **Finance Thresholds** | $200/month minimum for admission |
| **Admission Gates** | Require 2+ corroborating sources |
| **Domain Handling** | Infrastructure domain exclusions, alias rules |

### Performance Metrics

| Metric | Current Performance |
|--------|---------------------|
| **Classification Accuracy** | 98.5% |
| **Admission Accuracy** | 99.1% |
| **Shadow Detection** | 99.2% |
| **Zombie Detection** | 97.7% |
| **Combined Accuracy** | 98.8% |

*Validated against 17,000+ asset permutations across 37 edge case categories*

---

## Integration Points

### Upstream (Data Sources)

AOD accepts data via:
- Direct API integration
- File upload (CSV, JSON)
- Scheduled sync from SIEMs, CMDBs
- Real-time streaming (coming soon)

### Downstream (AutonomOS Platform)

AOD outputs feed directly into:
- **AAM:** Asset catalog drives connector provisioning
- **DCL:** Canonical entities for ontology mapping
- **Agents:** Classification data for FinOps/SecOps automation

---

## Deployment Options

| Option | Description | Best For |
|--------|-------------|----------|
| **SaaS** | Hosted at discover.autonomos.tech | Quick start, no infrastructure |
| **Private Cloud** | Dedicated tenant in AOS cloud | Data residency requirements |
| **On-Premise** | Self-hosted deployment | Air-gapped environments |

---

## Demo & Proof of Value

### Live Simulation

AOD includes a built-in simulation capability:

1. **Generate Chaos:** Farm creates realistic, messy enterprise data
2. **Process:** AOD ingests and correlates the data
3. **Validate:** Reconciliation proves accuracy against ground truth

This allows prospects to see AOD handle real-world complexity—not sanitized demo data.

### Proof of Value Engagement

Typical PoV timeline:

| Week | Activity |
|------|----------|
| 1 | Connect 2-3 data sources (SSO logs, expense data, network logs) |
| 2 | AOD processes and classifies |
| 3 | Review findings, quantify shadow IT and zombie spend |
| 4 | Present findings, discuss platform expansion |

---

## Competitive Differentiation

| Capability | AOD | Traditional ITAM | CASB/SaaS Management |
|------------|-----|------------------|---------------------|
| Multi-source correlation | Yes | Limited | No |
| Governance classification | Automatic | Manual | Partial |
| Finance-aware discovery | Yes | No | Limited |
| Zombie detection | Yes | No | Some |
| Platform integration | Native to AOS | Standalone | Standalone |
| AI/Agent ready | Yes | No | No |

---

## Roadmap

| Capability | Status | Description |
|------------|--------|-------------|
| **Snapshot-Based Discovery** | Available | Process point-in-time data exports from enterprise sources |
| **Multi-Source Correlation** | Available | Correlate signals across IdP, CMDB, Finance, Network |
| **Governance Classification** | Available | Automatic Shadow/Zombie/Governed classification |
| **Triage Workflow** | Available | Prioritized findings with acknowledge/reject actions |
| **Continuous Monitoring** | Roadmap | Real-time ingestion with streaming data sources |
| **Change Detection** | Roadmap | Track assets added/removed over time, alert on drift |
| **Scheduled Sync** | Roadmap | Automated periodic refresh from connected sources |
| **Triage State Persistence** | Roadmap | Maintain triage decisions across discovery runs |
| **Historical Trending** | Roadmap | Track Shadow IT and Zombie counts over time |

---

## Pricing

Contact sales for pricing based on:
- Number of employees
- Data sources connected
- Platform tier (AOD only vs full AOS)

---

## Contact

**Product Demo:** discover.autonomos.tech  
**Sales:** [Contact Information]  
**Documentation:** Available upon request

---

*AOD: Know what you own. Govern what runs. Connect with confidence.*
