# AOS Discover Policy Switches Reference

**Version:** 1.0.0  
**Last Updated:** 2026-01-14

This document describes all policy switches available in the AOS Discover Central Policy Switchboard. These settings control admission logic, classification behavior, and Farm synchronization.

---

## Table of Contents

1. [Activity Windows](#activity-windows)
2. [Finance Thresholds](#finance-thresholds)
3. [Admission Gates](#admission-gates)
4. [Scope Toggles](#scope-toggles)
5. [Fuzzy Matching](#fuzzy-matching)
6. [Vendor Inference](#vendor-inference)
7. [Query Limits](#query-limits)
8. [Exclusion Lists](#exclusion-lists)
9. [Farm Sync](#farm-sync)

---

## Activity Windows

Time windows for activity status calculations. These determine when assets are classified as RECENT, STALE, or inactive.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `discovery_activity_window_days` | integer | 90 | 1-365 | Days to consider for discovery activity |
| `zombie_window_days` | integer | 90 | 1-365 | Days of inactivity before asset is considered stale for zombie classification |
| `default_activity_window_days` | integer | 90 | 1-365 | Default activity window for shadow/zombie classification |

---

## Finance Thresholds

Financial thresholds for admission and findings generation. Controls when finance data triggers admission or findings.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `minimum_spend` | float | 200.00 | 0-100,000 | Minimum monthly spend (USD) for finance gate admission |
| `finance_gap_monthly_threshold` | float | 200.00 | 0-100,000 | Minimum monthly spend (USD) to trigger FINANCE_GAP finding |
| `finance_gap_annual_threshold` | float | 2,000.00 | 0-1,000,000 | Minimum annual spend (USD) to trigger FINANCE_GAP finding |

**Note on Recurring Finance:** These thresholds only apply to **recurring** finance (contracts/subscriptions with `is_recurring=True`). One-time purchases are excluded from:
- Zombie classification (requires ongoing finance + stale activity)
- Finance Gap findings (requires recurring spend with no governance)
- The "has_ongoing_finance" predicate used in derived classifications

The `is_recurring` flag is set on individual finance records at ingestion, not controlled by policy.

---

## Admission Gates

Switches controlling admission gate behavior. These determine what evidence is required for an asset to be admitted.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `noise_floor` | integer | 1 | 1-10 | Minimum number of discovery sources required for admission |
| `require_sso_for_idp` | boolean | true | - | Require SSO/SCIM for IdP-based governance |
| `require_valid_ci_type` | boolean | true | - | Require valid CI type for CMDB-based governance |
| `require_valid_lifecycle` | boolean | true | - | Require valid lifecycle status for CMDB governance |
| `min_discovery_sources_for_shadow` | integer | 2 | 1-10 | Minimum corroborating sources for shadow classification |
| `allow_finance_only_admission` | boolean | false | - | Allow finance-only admission without corroboration |
| `enable_vendor_propagation` | boolean | true | - | Enable vendor governance propagation from siblings |
| `finance_requires_discovery` | boolean | true | - | Require discovery evidence for finance admission |
| `require_corroboration` | boolean | true | - | Require 2+ sources for discovery-only admission |
| `stale_window_days` | integer | 30 | 1-365 | Days of inactivity before asset is considered stale |

### IdP Governance Gate (`require_sso_for_idp`)
Controls when IdP presence counts as "governed":
- **true**: Asset must have SSO, SCIM provisioning, OR be a service principal to count as HAS_IDP
- **false**: Any IdP presence counts as governed

### CMDB Governance Gate (`require_valid_ci_type`)
Controls when CMDB presence counts as "governed":
- **true**: CI type must be one of: `app`, `application`, `service`, `database`, `infra`, `infrastructure`, `server`, `system`
- **false**: Any CMDB presence counts as governed

**Valid CI Types:** `app`, `application`, `service`, `database`, `infra`, `infrastructure`, `server`, `system`

### Lifecycle Validation (`require_valid_lifecycle`)
Only applies when `require_valid_ci_type` is also true:
- **true**: Lifecycle status must be: `prod`, `production`, `staging`, `stage`, `live`, `active`
- **false**: Any lifecycle status is accepted

**Valid Lifecycles:** `prod`, `production`, `staging`, `stage`, `live`, `active`

### Finance Corroboration Gate (`allow_finance_only_admission`)
Controls whether finance evidence alone can admit an asset:
- **false** (default): Finance requires corroboration from IdP, CMDB, Cloud, OR 2+ discovery sources
- **true**: Finance alone (recurring spend) is sufficient for admission

When disabled (default behavior), assets with only finance evidence are rejected with "No admission criteria satisfied" unless they also have governance or sufficient discovery corroboration.

### Vendor Propagation (`enable_vendor_propagation`)
Controls whether governance can be inherited from vendor siblings:
- **true** (default): Vendor-propagated IdP/CMDB from sibling domains counts for admission
- **false**: Only direct IdP/CMDB matches count for governance

Example: When enabled, `googleapis.com` inherits HAS_IDP from "Google+" IdP record.

### Finance Discovery Requirement (`finance_requires_discovery`)
Controls whether finance-based admission needs discovery evidence:
- **true** (default): Finance must have governance or discovery corroboration
- **false**: Finance can admit without discovery evidence (reduces rejections)

Set to `false` to reduce rejection count for assets with valid finance but limited discovery.

### Discovery Corroboration (`require_corroboration`)
Controls the discovery source threshold for admission:
- **true** (default): Require 2+ discovery sources for discovery-only admission
- **false**: Honor the `noise_floor` setting (can be 1 source)

Set to `false` to allow single-source discovery when `noise_floor=1`.

### Stale Window (`stale_window_days`)
Number of days of inactivity before an asset is considered stale in admission logic:
- **Default**: 30 days
- **Range**: 1-365 days

Used in the Traffic Light provisioning logic to identify zombie candidates.

---

## Scope Toggles

Feature toggles for operational modes. These enable or disable major system behaviors.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `include_infra` | boolean | false | Include infrastructure assets in discovery results |
| `treat_directory_as_idp` | boolean | false | Treat directory services (AD, LDAP) as IdP |
| `use_policy_engine` | boolean | true | Use new policy engine for admission decisions |
| `late_binding_domain_merge` | boolean | true | Enable late-binding domain merge for multi-domain assets |

---

## Fuzzy Matching

Parameters for fuzzy name matching in correlation. Controls how aggressively the system matches similar names.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `max_edit_distance` | integer | 2 | 0-10 | Maximum edit distance for fuzzy name matching |
| `max_edit_ratio` | float | 0.2 | 0-1 | Maximum edit distance ratio (distance/max_length) |
| `min_name_length` | integer | 4 | 1-20 | Minimum name length to apply fuzzy matching |

---

## Vendor Inference

Parameters for vendor hypothesis inference.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `max_confidence` | float | 0.9 | 0-1 | Maximum confidence for vendor hypothesis (never fully authoritative) |

---

## Query Limits

Database and storage limits. Controls resource usage for queries and storage.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `max_observation_samples` | integer | 2,000 | 100-50,000 | Maximum observation samples to store per run |
| `default_rejection_limit` | integer | 1,000 | 100-50,000 | Default limit for rejection queries |
| `default_query_limit` | integer | 1,000 | 100-50,000 | Default limit for general queries |

---

## Exclusion Lists

Domain exclusion lists for admission filtering. Assets matching these domains are excluded from discovery.

### Custom Exclusions
Operator-managed domains to exclude from discovery:
- `platform.io`, `hub.io`, `data.io`, `cdn.com`, `edge.com`
- `global.com`, `api.co`, `app.co`, `pro.co`, `quick.net`
- `max.io`, `smart.io`, `sys.net`, `force.com`, `fast.io`
- `plus.net`, `cloud.net`, `tech.net`, `services.io`, `world.net`

### Banned Domains
System banned domains (major tech infrastructure):
- Google: `googleapis.com`, `gstatic.com`, `googleusercontent.com`
- Microsoft: `microsoft.com`, `microsoftonline.com`, `windows.net`, `azure.com`, `office.com`, `office365.com`
- Apple: `apple.com`, `icloud.com`
- CDN: `akamai.net`, `akamaized.net`, `cloudfront.net`
- AWS: `amazonaws.com`, `awsstatic.com`

### Infrastructure Domains
Infrastructure technology domains:
- Databases: `redis.io`, `redis.com`, `postgresql.org`, `mysql.com`, `mongodb.org`
- Container/Orchestration: `docker.com`, `kubernetes.io`
- Web servers: `nginx.org`, `apache.org`
- Languages: `golang.org`, `python.org`, `nodejs.org`, `npmjs.com`
- DevOps: `jenkins.io`, `terraform.io`, `hashicorp.com`
- Observability: `grafana.com`, `prometheus.io`, `elastic.co`

### Corporate Root Domains
Customer corporate marketing domains to exclude (operator-configured, empty by default).

---

## Farm Sync

Farm synchronization settings. Controls how AOS Discover communicates policy changes to Farm.

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `webhook_url` | string | "" | - | Farm webhook URL for policy change notifications |
| `auto_notify_on_change` | boolean | true | - | Automatically notify Farm when policy changes |
| `sync_interval_seconds` | integer | 0 | 0-3600 | Periodic sync interval (0 = disabled, Farm pulls on demand) |

---

## API Endpoints

### Read Policy
```
GET /api/v1/policy/master
```
Returns the complete policy configuration with metadata.

### Update Policy
```
PUT /api/v1/policy/master
```
Updates policy settings. Automatically triggers Farm webhook if `auto_notify_on_change` is enabled.

### Manual Farm Notification
```
POST /api/v1/policy/notify-farm
```
Manually trigger a policy sync notification to Farm.

---

## UI Access

The Policy Switchboard is accessible via:
- **Main UI:** Click the "Policy" tab in the navigation bar
- **Direct URL:** `/static/policy-switchboard.html`
- **Standalone:** `/switchboard` (redirects to switchboard page)
