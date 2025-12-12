# Farm → AOD Integration Guide

**Version:** 1.2  
**Last Updated:** December 12, 2025  
**Status:** Production Ready

---

## Overview

This document specifies how AOD should integrate with Farm to pull synthetic enterprise data for testing discovery, normalization, and quality metrics.

### Architecture Philosophy

| System | Role | Responsibility |
|--------|------|----------------|
| **Farm** | Synthetic Enterprise | Generates realistic heterogeneous enterprise data with configurable archetypes |
| **AOD** | Discovery Engine | Schema-agnostic engine that pulls from Farm, interprets data, and applies discovery/classification logic |

**Key Principle:** AOD pulls from Farm (not push). Farm is a passive data source that responds to AOD requests.

---

## Surfaces vs Sources: Key Distinction

Farm exposes two distinct data concepts that serve different testing modules:

### Surfaces (8 telemetry lenses for AOD)

Surfaces are **IT detection signals** - telemetry lenses that AOD uses to discover and classify assets:

| Surface | Description | Signals |
|---------|-------------|---------|
| `idp` | Identity Provider events | SSO logins, auth methods, user counts |
| `billing` | Financial/Procurement | Invoices, contracts, spend |
| `saas_api` | SaaS API integrations | OAuth tokens, API calls |
| `edr` | Endpoint Detection | Processes, files, device info |
| `browser` | Browser extensions | Web apps accessed, extensions |
| `network` | Network logs | DNS, firewall, traffic patterns |
| `cmdb` | Config Management DB | Asset records, relationships |
| `observability` | APM/Monitoring | Traces, logs, metrics |

### Sources (34 business systems for DCL/AAM)

Sources are **business data systems** - the systems-of-record where customer, transaction, and product data lives:

| Category | Count | Examples |
|----------|-------|----------|
| CRM | 3 | Salesforce, HubSpot, Dynamics 365 |
| ERP | 3 | NetSuite, Oracle ERP, SAP S/4HANA |
| Billing | 5 | Stripe, Chargebee, Recurly, Zuora, Paddle |
| Payment | 4 | PayPal, Square, Braintree, Adyen |
| Accounting | 3 | QuickBooks, Xero, FreshBooks |
| Warehouse | 11 | Snowflake, BigQuery, Redshift, Databricks |
| Custom DB | 4 | PostgreSQL, MySQL, MongoDB, Redis |
| Legacy | 1 | Legacy CSV exports |

**Source Types:**
- `SYSTEM_OF_RECORD` (23): Authoritative systems where entities are created
- `CURATED` (6): Warehouse tables with modeled data
- `AGGREGATED` (2): Rollup tables for reporting
- `CONSUMER_ONLY` (3): BI tools that read data (Tableau, Looker, Power BI)

**DCL-Eligible:** 29 sources (SYSTEM_OF_RECORD + CURATED only)

### Canonical Source Registry

All testing clients (AOD, DCL, AAM) should consume from the same source registry:

```
GET /api/farm/sources        → All 34 sources
GET /api/farm/sources/dcl    → 29 DCL-eligible sources
```

The AOD enterprise snapshot now includes both surfaces AND business_sources:

```json
{
  "surfaces": { /* 8 telemetry lenses */ },
  "business_sources": [
    {
      "source_id": "salesforce_crm",
      "name": "Salesforce CRM",
      "source_type": "SYSTEM_OF_RECORD",
      "category": "crm",
      "vendor": "Salesforce",
      "entities": ["Account", "Contact", "Opportunity", "Lead"],
      "is_primary": true
    }
  ]
}
```

---

## Base URL

```
https://<farm-deployment-url>
```

---

## Farm Endpoints (Called by AOD)

### 1. POST `/api/farm/enterprise/new`

Creates a new synthetic enterprise with all surface data.

**Request Body:**
```json
{
  "archetype": "hybrid_sprawl",
  "scale": "medium"
}
```

**Available Archetypes:**
| Archetype | Description | Shadow IT Rate |
|-----------|-------------|----------------|
| `hybrid_sprawl` | Multi-cloud with legacy systems | ~35% |
| `k8s_mesh` | Kubernetes-native microservices | ~25% |
| `legacy_monolith` | On-premises dominated | ~15% |
| `saas_heavy` | SaaS-first organization | ~30% |
| `startup_lean` | Minimal infrastructure startup | ~20% |
| `regulated_bank` | Financial services with compliance | ~10% |
| `healthcare_network` | Healthcare with HIPAA requirements | ~12% |
| `retail_chain` | Retail with POS and inventory | ~25% |
| `media_streaming` | Content delivery infrastructure | ~20% |
| `manufacturing_iot` | Industrial IoT and OT systems | ~18% |

**Scale Reference:**
| Scale | Asset Count |
|-------|-------------|
| small | ~30 assets |
| medium | ~100 assets |
| large | ~300 assets |

**Response:**
```json
{
  "success": true,
  "tenant_id": "cyberhelix-abc123",
  "company_name": "CyberHelix",
  "industry": "Technology",
  "archetype": "k8s_mesh",
  "generated_at": "2025-12-05T01:31:39.340Z",
  "asset_count": 29,
  "surfaces": {
    "idp": {
      "surface": "idp",
      "tenant": "cyberhelix-abc123",
      "timestamp": "2025-12-05T01:31:39.177Z",
      "evidence": [
        {
          "entity_hint": "api-gateway-production",
          "vendor_hint": ".NET",
          "signals": {
            "farm_asset_id": "k8s_mesh_svc_001",
            "sso_enabled": true,
            "user_count": 159,
            "last_auth": "2025-12-02T16:12:40.859Z",
            "auth_method": "SAML",
            "owner_email": "security@company.com",
            "auth_event_count": 6819
          }
        }
      ]
    },
    "saas_api": { ... },
    "cmdb": { ... },
    "billing": { ... },
    "edr": { ... },
    "browser": { ... },
    "network": { ... },
    "observability": { ... }
  }
}
```

---

### 2. GET `/api/farm/enterprise/{tenant_id}/poll?since=<timestamp>`

Returns delta changes since last poll. Simulates real-world enterprise drift.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| since | string | Yes | ISO 8601 timestamp (e.g., `2025-12-04T00:00:00Z`) |

**Response:**
```json
{
  "success": true,
  "tenant_id": "cyberhelix-abc123",
  "poll_number": 3,
  "since": "2025-12-04T00:00:00Z",
  "until": "2025-12-05T02:00:00.000Z",
  "changes": {
    "added": [
      {
        "entity_hint": "Notion",
        "vendor_hint": "Notion Labs",
        "signals": {
          "farm_asset_id": "cyberhelix-abc123_drift_1733367000_0",
          "user_count": 45,
          "sso_enabled": false,
          "is_shadow": true
        }
      }
    ],
    "modified": [
      {
        "entity_hint": "Salesforce CRM",
        "vendor_hint": "Salesforce",
        "signals": {
          "farm_asset_id": "k8s_mesh_saas_001",
          "modification_type": "contract_renewed",
          "modified_at": "2025-12-05T01:31:57.899Z",
          "contract_id": "CNT-xyz789",
          "renewal_date": "2026-12-05T01:31:57.899Z"
        }
      }
    ],
    "deleted": [
      {
        "farm_asset_id": "k8s_mesh_app_007",
        "entity_hint": "legacy-reporting-tool",
        "vendor_hint": "Internal",
        "asset_type": "application",
        "deleted_at": "2025-12-05T02:00:00.000Z"
      }
    ]
  },
  "drift_scenarios_applied": [
    "new_shadow_it",
    "usage_growth",
    "asset_retirement"
  ],
  "surfaces_affected": ["idp", "billing", "cmdb"]
}
```

**Drift Scenarios:**
| Scenario | Description | Effect |
|----------|-------------|--------|
| `new_shadow_it` | New unauthorized apps appear | Adds assets with edge-only lens coverage |
| `usage_growth` | Existing apps gain users | Increases user_count, spend metrics |
| `asset_retirement` | Old apps decommissioned | Marks assets as deleted |
| `ownership_change` | Apps change owners | Updates owner/owner_email fields |
| `sso_enablement` | Shadow IT gets sanctioned | Adds IdP lens coverage |
| `license_renewal` | Contracts renewed | Updates contract dates and amounts |

---

### 3. GET `/api/farm/enterprise/{tenant_id}/ground-truth`

Returns authoritative state of all assets for validation/comparison.

**Response:**
```json
{
  "success": true,
  "tenant_id": "cyberhelix-abc123",
  "company_name": "CyberHelix",
  "ground_truth": {
    "version": "2.0.0",
    "last_updated": "2025-12-05T01:31:59.203Z",
    "scenario_id": "cyberhelix-abc123",
    "scenario_version": "v2",
    "company_name": "CyberHelix",
    "digital_twin_id": "k8s_mesh",
    "expected_assets": [
      {
        "farm_asset_id": "k8s_mesh_db_001",
        "asset_name": "users-postgresql-production",
        "asset_kind": "db",
        "catalog_asset_type": "database",
        "lifecycle_state": "CATALOGED",
        "lifecycle_stage": "stable",
        "business_domain": "operations",
        "system_role": "system_of_record",
        "expected_priority": "critical",
        "expected_risk_level": "critical",
        "is_shadow_it": false,
        "shadow_scenario": "managed",
        "shadow_reasons": [],
        "is_zombie": false,
        "has_data_conflicts": false,
        "conflict_types": [],
        "rules_triggered": [],
        "parked_reason": null,
        "vendor": "PostgreSQL",
        "provider": "aws",
        "environment": "production",
        "owner": "Alex Kim",
        "owner_email": "alex.kim@company.com",
        "owner_team": "Data Engineering",
        "sources": ["cloud_org", "cmdb", "network_logs"]
      }
    ]
  }
}
```

**Ground Truth Fields for Blocking/Non-Blocking Classification:**

| Field | Type | Description |
|-------|------|-------------|
| `rules_triggered` | string[] | All rule IDs triggered for this asset |
| `conflict_types` | string[] | Conflict types detected |
| `has_data_conflicts` | boolean | True if any conflicts exist |
| `parked_reason` | string | Blocking rule ID if asset is PARKED, null if CATALOGED |
| `lifecycle_state` | string | `CATALOGED` (no blocking rules) or `PARKED` (has blocking rules) |

**Ownership Fields (Person-Centric Model):**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | string | Person's name (e.g., "Alex Kim") - null for shadow IT |
| `owner_email` | string | Person's email - null for shadow IT |
| `owner_team` | string | Team/squad name (e.g., "Data Engineering") - null for shadow IT |
| `business_domain` | string | Canonical domain: `finance`, `gtm`, `product_usage`, `operations`, `hr`, `legal_risk`, `it_security`, `unknown` |

---

### 4. GET `/api/farm/sources`

Returns the canonical source registry - all 34 business sources available to ANY testing client (AOD, DCL, AAM).

**Response:**
```json
{
  "success": true,
  "total": 34,
  "by_type": {
    "SYSTEM_OF_RECORD": 23,
    "CURATED": 6,
    "AGGREGATED": 2,
    "CONSUMER_ONLY": 3
  },
  "by_category": {
    "crm": 3,
    "erp": 3,
    "billing": 5,
    "payment": 4,
    "accounting": 3,
    "warehouse": 11,
    "custom_db": 4,
    "legacy": 1
  },
  "dcl_source_count": 29,
  "sources": [
    {
      "source_id": "salesforce_crm",
      "name": "Salesforce CRM",
      "description": "Primary CRM for sales and customer management",
      "source_type": "SYSTEM_OF_RECORD",
      "category": "crm",
      "vendor": "Salesforce",
      "connection_type": "api",
      "entities": ["Account", "Contact", "Opportunity", "Lead"],
      "trust_score": 95,
      "data_quality_score": 90,
      "is_primary": true
    }
  ]
}
```

---

### 5. GET `/api/farm/sources/dcl`

Returns only DCL-eligible sources (SYSTEM_OF_RECORD + CURATED = 29 sources).

---

### 6. GET `/api/farm/enterprise/{tenant_id}/sources`

Returns source information for a specific tenant with record counts.

---

### 7. GET `/api/farm/enterprise/{tenant_id}`

Returns current enterprise state and metadata.

**Response:**
```json
{
  "success": true,
  "tenant_id": "cyberhelix-abc123",
  "company_name": "CyberHelix",
  "industry": "Technology",
  "archetype": "k8s_mesh",
  "scale": "small",
  "last_snapshot_at": "2025-12-05T01:35:02.381Z",
  "snapshot_version": 3,
  "poll_count": 2,
  "asset_count": 29,
  "by_type": {
    "host": 8,
    "saas": 5,
    "service": 5,
    "database": 3,
    "application": 8
  },
  "by_surface": {
    "idp": 29,
    "cmdb": 26,
    "billing": 20,
    "edr": 16,
    "browser": 13,
    "network": 21,
    "observability": 13,
    "saas_api": 5
  }
}
```

---

### 5. GET `/api/farm/enterprises`

Lists all generated enterprises.

**Response:**
```json
{
  "success": true,
  "count": 3,
  "enterprises": [
    {
      "tenant_id": "cyberhelix-abc123",
      "company_name": "CyberHelix",
      "industry": "Technology",
      "archetype": "k8s_mesh",
      "scale": "small",
      "asset_count": 29,
      "last_snapshot_at": "2025-12-05T01:35:02.381Z",
      "snapshot_version": 3
    }
  ]
}
```

---

### 6. POST `/api/farm/runs`

**NEW:** Allows AOD to report its discovery runs back to Farm for tracking in Run History.

**Request Body:**
```json
{
  "enterpriseTenantId": "phoenix-systems-healthcare",
  "archetype": "hybrid_sprawl",
  "scale": "medium",
  "status": "success",
  "assetCount": 83,
  "surfaceCount": 8,
  "runKind": "aod_full_pull",
  "message": "AOD discovered 83 assets across Phoenix Systems Healthcare",
  "durationMs": 2500,
  "metrics": {
    "shadowItCount": 12,
    "conflictCount": 5
  }
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| enterpriseTenantId | string | Yes | The tenant/company ID (e.g., "phoenix-systems-healthcare") |
| archetype | string | No | Digital twin archetype used |
| scale | string | No | Scale of enterprise (small/medium/large) |
| status | string | No | Run status: "success", "failed", "running" (default: "success") |
| assetCount | number | No | Total assets discovered |
| surfaceCount | number | No | Number of surfaces processed (default: 8) |
| runKind | string | No | Type of run: "aod_full_pull", "aod_incremental_poll" (default: "aod_full_pull") |
| message | string | No | Human-readable description of the run |
| durationMs | number | No | Duration of run in milliseconds |
| metrics | object | No | Additional metrics (e.g., shadowItCount, conflictCount) |

**Response:**
```json
{
  "success": true,
  "run_id": "0fd5f9d2-46eb-40c5-9b86-dd3a45a7f92c",
  "message": "Run recorded for phoenix-systems-healthcare"
}
```

---

## Data Surfaces (Lens Types)

Farm generates evidence across 8 lens types that AOD ingests:

### Control Plane Lenses
| Lens | Description | Key Signals |
|------|-------------|-------------|
| **idp** | Identity provider integrations | `sso_enabled`, `user_count`, `last_auth`, `auth_method` |
| **cmdb** | Configuration management database | `ci_id`, `ci_class`, `in_cmdb`, `has_metadata`, `parked_reason`, `has_data_conflicts`, `conflict_types`, `rules_triggered`, `is_shadow_it`, `anomaly_score`, `prob_kind` |
| **saas_api** | SaaS API connections | `api_connected`, `oauth_scopes`, `api_call_count` |

**CMDB Conflict/Rule Signals (v1.2):**

AOD should read blocking/non-blocking classification from `surfaces.cmdb.evidence[*].signals`:

| Signal | Type | Description |
|--------|------|-------------|
| `parked_reason` | string | Blocking rule ID if asset is PARKED (e.g., `ONT_AMBIGUOUS_TYPE`) |
| `has_data_conflicts` | boolean | True if asset has any conflicts |
| `conflict_types` | string[] | Array of conflict types (e.g., `["SOR_CONFLICT"]`) |
| `rules_triggered` | string[] | All rule IDs triggered (blocking + non-blocking) |
| `is_shadow_it` | boolean | Shadow IT flag |
| `anomaly_score` | number | 0.0-1.0, ≥0.4 indicates OPS_* risk |
| `prob_kind` | number | 0.0-1.0, <0.5 indicates low confidence in asset type |

**Blocking Rules (Asset PARKED):**
- `ONT_SOR_CONFLICT` - Multiple systems claim System of Record
- `ONT_AMBIGUOUS_TYPE` - Cannot determine asset type
- `DATA_SCHEMA_DRIFT` - Schema structure incompatible

**Non-Blocking Rules (Asset CATALOGED with Findings):**
- `GOV_NO_OWNER`, `GOV_ORPHAN` - Governance gaps
- `SEC_WEAK_AUTH`, `SEC_PUBLIC_EXPOSED` - Security findings
- `OPS_ZOMBIE_IN_PROD`, `OPS_STALE_CONFIG` - Operational issues
- `SHADOW_EDGE_ONLY`, `SHADOW_NO_CONTRACT` - Shadow IT indicators

### Edge Lenses
| Lens | Description | Key Signals |
|------|-------------|-------------|
| **billing** | Finance/expense data | `contract_id`, `monthly_cost`, `license_count` |
| **edr** | Endpoint detection agents | `detected_on_endpoints`, `endpoint_count`, `agent_version` |
| **browser** | Browser extension telemetry | `visit_count`, `unique_users`, `data_uploaded_mb` |
| **network** | DNS logs, network flows | `dns_queries`, `bytes_transferred`, `protocols` |
| **observability** | APM, logging platforms | `traces_enabled`, `span_count`, `error_rate` |

---

## Stable Identity: farm_asset_id

The `farm_asset_id` is the **ONLY** stable identifier for correlating assets across:
- Initial full pull
- Incremental deltas (additions, modifications, deletions)
- Ground truth comparison

**Format:** `{archetype}_{assetType}_{index}` or `{tenantId}_drift_{timestamp}_{index}`

**Examples:**
- `k8s_mesh_db_001` - Database from initial generation
- `k8s_mesh_svc_003` - Service from initial generation
- `cyberhelix-abc123_drift_1733367000_0` - Asset added via drift

**Critical for AOD:**
1. Extract `farm_asset_id` from `signals.farm_asset_id`
2. Use it to match discovered assets against ground truth
3. Track deletions by `farm_asset_id` to remove from catalog

---

## Shadow IT Detection

Farm generates assets with realistic shadow IT patterns. AOD should determine Shadow IT based on **lens coverage patterns**:

| Condition | Result | Reason Code |
|-----------|--------|-------------|
| Edge lenses only, no control plane | `is_shadow_it = TRUE` | `no_idp`, `no_cmdb` |
| Finance spend but no technical instrumentation | `is_shadow_it = TRUE` | `finance_only` |
| Personal email signup (gmail, yahoo, etc.) | `is_shadow_it = TRUE` | `personal_email` |
| Only 1-2 users | `is_shadow_it = TRUE` | `few_users` |
| No owner assigned | `is_shadow_it = TRUE` | `no_owner` |

Ground truth provides `is_shadow_it` and `shadow_reasons` for validation.

---

## Recommended Integration Flow

### AOD Endpoints to Implement

Based on the AOD spec, implement these wrapper endpoints:

#### POST `/farm/ingest/full-pull`

```
1. Call Farm: POST /api/farm/enterprise/new
2. Store tenant_id, company_name in AOD's farm_enterprises table
3. Convert surfaces to AOD evidence records
4. Run discovery pipeline
5. Return summary with counts
```

#### POST `/farm/ingest/incremental-poll`

```
1. Look up existing enterprise by farm_tenant_id
2. Call Farm: GET /api/farm/enterprise/{tenant_id}/poll?since=<last_poll_at>
3. Process changes (add/modify/delete assets)
4. Update last_poll_at timestamp
5. Return summary with change counts
```

---

## Quality Metrics Computation

Using ground truth, compute:

```
Recall = |discovered ∩ expected| / |expected|
Precision = |discovered ∩ expected| / |discovered|
F1 = 2 * (precision * recall) / (precision + recall)
```

Additional metrics from ground truth:
- **Type Accuracy**: % of assets with correct `asset_kind`
- **Priority Agreement**: % matching `expected_priority`
- **Shadow IT Detection**: % of `is_shadow_it=true` correctly flagged
- **Conflict Detection**: % of `has_data_conflicts=true` identified

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 201 | Enterprise created |
| 400 | Bad request (invalid timestamp, missing parameters) |
| 404 | Enterprise not found |
| 500 | Server error |

**Example Error Response:**
```json
{
  "success": false,
  "error": "Invalid timestamp: not-a-date. Expected ISO 8601 format."
}
```

---

## Example API Calls

```bash
# Full Pull - Create new enterprise
curl -X POST http://localhost:5000/api/farm/enterprise/new \
  -H "Content-Type: application/json" \
  -d '{"archetype": "hybrid_sprawl", "scale": "medium"}'

# Get enterprise details
curl http://localhost:5000/api/farm/enterprise/cyberhelix-abc123

# Incremental Poll
curl "http://localhost:5000/api/farm/enterprise/cyberhelix-abc123/poll?since=2025-12-04T00:00:00Z"

# Get ground truth
curl http://localhost:5000/api/farm/enterprise/cyberhelix-abc123/ground-truth

# List all enterprises
curl http://localhost:5000/api/farm/enterprises
```

---

## Company Names

Farm generates unique, memorable company names for each enterprise:

**Tech:** CyberHelix, VoltStream, NexaCloud, QuantumByte, DataForge, CloudPulse, SynthAI, ByteWave

**Healthcare:** MedPulse, HealthNexus, CareBridge, VitalSync, BioMetrics

**Finance:** CapitalNexus, FinanceFlow, WealthGuard, SecureBank

**Retail:** ShopWave, RetailNexus, CommerceHub

Each name is paired with a matching digital twin archetype for realistic enterprise simulation.

---

*Document generated from Farm-AOD Integration v1.1*
