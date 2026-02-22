# AOD Internal Test Harness

## Overview

The AOD test harness enables **autonomous development and debugging** by providing a closed-loop reconciliation system with Farm (the test oracle). This document describes how the harness works, the data contracts, and how to use it for autonomous testing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FARM (Test Oracle)                          │
│  ┌─────────────┐    ┌─────────────────┐    ┌───────────────────────┐   │
│  │  Snapshot   │    │   __expected__  │    │   Reconciliation UI   │   │
│  │  Generator  │───▶│    section      │    │   (computes diffs)    │   │
│  │  (17k+ permutations) │             │    └───────────────────────┘   │
│  └─────────────┘    └─────────────────┘              ▲                  │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ GET /api/snapshots/{id}
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              AOD (System Under Test)                     │
│  ┌─────────────┐    ┌─────────────────┐    ┌───────────────────────┐   │
│  │ /runs/      │    │    Pipeline     │    │ /debug/aod-agent-     │   │
│  │ from-farm   │───▶│    Executor     │───▶│ reconcile             │   │
│  └─────────────┘    └─────────────────┘    └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Actual Results │
                    │  shadow_actual  │
                    │  zombie_actual  │
                    │  reason_codes   │
                    └─────────────────┘
```

---

## Key Concepts

### Farm: The Ground Truth

**Farm** is a separate service that generates test snapshots containing realistic enterprise data. Each snapshot includes:

1. **Discovery observations** - Browser/network logs showing SaaS usage
2. **IdP records** - SSO/SCIM data from identity providers
3. **CMDB records** - Asset registry entries
4. **Finance transactions** - Expense/billing data

Critically, each snapshot also contains an `__expected__` section with Farm's ground truth:

```json
{
  "meta": {
    "tenant_id": "HelixSystems-K5PD",
    "snapshot_id": "d19678b2-4bf9-4ed3-8bab-32347223ae1b",
    "schema_version": "farm.v1"
  },
  "discovery_observations": [...],
  "idp_records": [...],
  "cmdb_records": [...],
  "finance_transactions": [...],
  
  "__expected__": {
    "shadow_expected": [
      {"asset_key": "notion.so", "reason": "NO_IDP|NO_CMDB|NO_VENDOR_GOVERNED"},
      {"asset_key": "airtable.com", "reason": "NO_IDP|NO_CMDB"}
    ],
    "zombie_expected": [
      {"asset_key": "dropbox.com", "reason": "IDP_GOVERNED|NO_ACTIVITY_365D"},
      {"asset_key": "slack.com", "reason": "CMDB_GOVERNED|NO_ACTIVITY_365D"}
    ]
  }
}
```

### Test Tenants

Farm provides three standard test tenants with different edge case distributions:

| Tenant | ID | Focus Areas |
|--------|-----|-------------|
| **HelixSystems** | `HelixSystems-K5PD` | General coverage, IdP edge cases |
| **CyberWorks** | `CyberWorks-UJRK` | Finance gaps, vendor governance |
| **InfoWorks** | `InfoWorks-ZQF9` | CMDB gaps, duplication risks |

---

## Test Flow

### Step 1: Fetch Snapshot from Farm

```bash
# Farm URL (autoscale - may take 10-15s on cold start)
FARM_URL="https://63971109-a901-48bc-a71f-89583b2e11d4-00-1do0vncksilxt.janeway.replit.dev"

# Get latest snapshot for a tenant
curl "$FARM_URL/api/snapshots?tenant_id=HelixSystems-K5PD&limit=1"
```

### Step 2: Create AOD Run from Snapshot

```bash
# Create run directly from Farm snapshot
curl -X POST "http://localhost:5000/api/runs/from-farm" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "HelixSystems-K5PD",
    "snapshot_id": "d19678b2-4bf9-4ed3-8bab-32347223ae1b"
  }'

# Response:
{
  "run_id": "run_abc123def456",
  "tenant_id": "HelixSystems-K5PD",
  "status": "completed",
  "counts": {
    "assets_admitted": 847,
    "findings_generated": 312
  }
}
```

### Step 3: Get AOD Actual Results

```bash
# Emit AOD's actual classifications
curl -X POST "http://localhost:5000/api/debug/aod-agent-reconcile" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "run_abc123def456"}'

# Response:
{
  "run_id": "run_abc123def456",
  "shadow_actual": ["notion.so", "airtable.com", "figma.com"],
  "zombie_actual": ["dropbox.com", "slack.com"],
  "admission_actual": {
    "notion.so": "admitted",
    "google.com": "rejected"
  },
  "actual_reason_codes": {
    "notion.so": ["SHADOW", "NO_IDP", "NO_CMDB"],
    "dropbox.com": ["ZOMBIE", "IDP_GOVERNED", "NO_ACTIVITY"]
  }
}
```

### Step 4: Compare Expected vs Actual

```python
# Autonomous reconciliation logic
import json

# Load Farm snapshot (contains __expected__)
with open('snapshot.json') as f:
    snapshot = json.load(f)

# Load AOD actual results
with open('actual.json') as f:
    actual = json.load(f)

# Extract expected sets
expected = snapshot.get('__expected__', {})
shadow_expected = set(item['asset_key'] for item in expected.get('shadow_expected', []))
zombie_expected = set(item['asset_key'] for item in expected.get('zombie_expected', []))

# Extract actual sets
shadow_actual = set(actual.get('shadow_actual', []))
zombie_actual = set(actual.get('zombie_actual', []))

# Compute accuracy
shadow_matched = shadow_expected & shadow_actual
zombie_matched = zombie_expected & zombie_actual

shadow_missed = shadow_expected - shadow_actual  # False negatives
shadow_extra = shadow_actual - shadow_expected   # False positives
zombie_missed = zombie_expected - zombie_actual
zombie_extra = zombie_actual - zombie_expected

shadow_accuracy = len(shadow_matched) / len(shadow_expected) * 100
zombie_accuracy = len(zombie_matched) / len(zombie_expected) * 100
combined_accuracy = (len(shadow_matched) + len(zombie_matched)) / \
                    (len(shadow_expected) + len(zombie_expected)) * 100

print(f"Shadow: {len(shadow_matched)}/{len(shadow_expected)} ({shadow_accuracy:.1f}%)")
print(f"Zombie: {len(zombie_matched)}/{len(zombie_expected)} ({zombie_accuracy:.1f}%)")
print(f"Combined: {combined_accuracy:.1f}%")
```

---

## API Reference

### POST /api/runs/from-farm

Creates a pipeline run by fetching a snapshot from Farm.

**Request:**
```json
{
  "tenant_id": "HelixSystems-K5PD",
  "snapshot_id": "d19678b2-4bf9-4ed3-8bab-32347223ae1b",
  "farm_base_url": "https://..."  // Optional, uses env FARM_URL if omitted
}
```

**Response:**
```json
{
  "run_id": "run_abc123def456",
  "tenant_id": "HelixSystems-K5PD",
  "status": "completed",
  "counts": {
    "assets_admitted": 847,
    "findings_generated": 312,
    "shadow_count": 45,
    "zombie_count": 12
  }
}
```

### POST /api/debug/aod-agent-reconcile

Emits AOD's actual classification results for a run.

**Design Principle:** Farm owns reconciliation. AOD only emits its "actual" output - it never consumes Farm's expected data.

**Request:**
```json
{
  "run_id": "run_abc123def456"
}
```

**Response:**
```json
{
  "run_id": "run_abc123def456",
  "shadow_actual": ["notion.so", "airtable.com"],
  "zombie_actual": ["dropbox.com"],
  "admission_actual": {
    "notion.so": "admitted",
    "microsoft.com": "admitted",
    "cdn.cloudflare.com": "rejected"
  },
  "actual_reason_codes": {
    "notion.so": ["SHADOW", "NO_IDP", "NO_CMDB", "NO_VENDOR_GOVERNED"],
    "dropbox.com": ["ZOMBIE", "IDP_GOVERNED", "NO_ACTIVITY_365D"]
  },
  "asset_details": {
    "notion.so": {
      "canonical_key": "notion.so",
      "classification": "shadow",
      "governance_signals": ["discovery_only"],
      "lens_match_debug": {...}
    }
  }
}
```

### POST /api/reconcile/explain-nonflag

Farm can ask AOD why an asset was NOT flagged (for debugging missed classifications).

**Request:**
```json
{
  "snapshot_id": "d19678b2-...",
  "ask_type": "zombie",
  "asset_keys": ["dropbox.com", "slack.com"]
}
```

**Response:**
```json
{
  "explanations": {
    "dropbox.com": {
      "classified_as": "governed",
      "reason": "IDP_GOVERNED with recent activity",
      "last_activity": "2026-01-15",
      "governance_signals": ["has_sso", "cmdb_registered"]
    }
  }
}
```

---

## Autonomous Testing Script

Here's a complete script for autonomous testing:

```bash
#!/bin/bash
# autonomous_test.sh - Run reconciliation across all test tenants

FARM_URL="https://63971109-a901-48bc-a71f-89583b2e11d4-00-1do0vncksilxt.janeway.replit.dev"
AOD_URL="http://localhost:5000"

TENANTS=("HelixSystems-K5PD" "CyberWorks-UJRK" "InfoWorks-ZQF9")

for tenant in "${TENANTS[@]}"; do
  echo "=== Testing $tenant ==="
  
  # Get latest snapshot
  snapshot_id=$(curl -s "$FARM_URL/api/snapshots?tenant_id=$tenant&limit=1" | \
                python3 -c "import json,sys; print(json.load(sys.stdin)['snapshots'][0]['id'])")
  
  # Fetch full snapshot (for __expected__)
  curl -s "$FARM_URL/api/snapshots/$snapshot_id" > /tmp/${tenant}_snapshot.json
  
  # Create AOD run
  run_response=$(curl -s -X POST "$AOD_URL/api/runs/from-farm" \
    -H "Content-Type: application/json" \
    -d "{\"tenant_id\": \"$tenant\", \"snapshot_id\": \"$snapshot_id\"}")
  
  run_id=$(echo "$run_response" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")
  
  # Get actual results
  curl -s -X POST "$AOD_URL/api/debug/aod-agent-reconcile" \
    -H "Content-Type: application/json" \
    -d "{\"run_id\": \"$run_id\"}" > /tmp/${tenant}_actual.json
  
  # Compute accuracy
  python3 << EOF
import json

with open('/tmp/${tenant}_snapshot.json') as f:
    snapshot = json.load(f)
with open('/tmp/${tenant}_actual.json') as f:
    actual = json.load(f)

expected = snapshot.get('__expected__', {})
shadow_exp = set(i['asset_key'] for i in expected.get('shadow_expected', []))
shadow_act = set(actual.get('shadow_actual', []))
zombie_exp = set(i['asset_key'] for i in expected.get('zombie_expected', []))
zombie_act = set(actual.get('zombie_actual', []))

s_match = len(shadow_exp & shadow_act)
z_match = len(zombie_exp & zombie_act)
combined = (s_match + z_match) / (len(shadow_exp) + len(zombie_exp)) * 100

print(f"Shadow: {s_match}/{len(shadow_exp)} ({s_match/len(shadow_exp)*100:.1f}%)")
print(f"Zombie: {z_match}/{len(zombie_exp)} ({z_match/len(zombie_exp)*100:.1f}%)")
print(f"Combined: {combined:.1f}%")

# Show misses if any
missed_shadow = shadow_exp - shadow_act
if missed_shadow:
    print(f"Missed shadows: {list(missed_shadow)[:5]}...")
EOF

  echo ""
done
```

---

## Debugging Discrepancies

### Check lens_match_debug

Every asset includes debug info showing HOW matches were made:

```json
{
  "notion.so": {
    "lens_match_debug": {
      "idp_match": null,
      "cmdb_match": null,
      "finance_match": {"method": "domain", "matched_to": "notion.so"},
      "governance_assertion": "none"
    }
  }
}
```

### Check Snapshot Drift

Farm snapshots regenerate when Farm code changes. Use this endpoint to detect drift:

```bash
curl "http://localhost:5000/api/debug/snapshot-drift-check?run_id=run_abc123"
```

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Many missed shadows | IdP matching too permissive | Check `trust_heuristic_matches` policy |
| Many extra shadows | IdP matching too strict | Check domain-to-vendor mappings |
| Zombie accuracy drops | Activity window mismatch | Check `zombie_activity_window_days` |
| Sudden accuracy drop | Snapshot regenerated | Re-run test with fresh snapshot |

---

## Policy Configuration

The test harness respects policy settings in `config/policy_master.json`:

```json
{
  "idp_governance": {
    "trust_heuristic_matches": false,  // Strict mode (Farm default)
    "heuristic_requires_sso": true
  },
  "zombie_detection": {
    "activity_window_days": 365
  },
  "admission": {
    "require_corroboration": true,
    "minimum_spend_threshold": 0
  }
}
```

### Strict vs Loose IdP Matching

| Policy | `trust_heuristic_matches` | Behavior |
|--------|---------------------------|----------|
| **Strict** | `false` | Only domain matches grant governance. Heuristic (fuzzy/name) = enrichment only. |
| **Loose** | `true` | Heuristic matches CAN grant governance. Reduces alerts but may hide shadow IT. |

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `FARM_URL_PROD` | Production Farm URL | farmv2.onrender.com |
| `FARM_URL_DEV` | Development Farm URL | Replit dev URL |
| `FARM_URL_MODE` | Which URL to use: `prod`, `dev`, `auto` | `auto` |
| `DATABASE_URL` | PostgreSQL connection | Replit-managed |

---

## Data Contract: Reason Codes

AOD emits standardized reason codes for each classification:

### Governance Reason Codes
- `HAS_IDP` - Has SSO integration in IdP
- `HAS_CMDB` - Registered in asset registry
- `VENDOR_GOVERNED` - Vendor-managed lifecycle (e.g., Microsoft 365)
- `NO_IDP` - No identity governance
- `NO_CMDB` - Not in asset registry
- `NO_VENDOR_GOVERNED` - Not vendor-managed

### Classification Reason Codes
- `SHADOW` - Asset lacks governance (shadow IT)
- `ZOMBIE` - Governed but inactive (abandoned)
- `GOVERNED` - Has active governance
- `ADMITTED` - Passed admission gates
- `REJECTED` - Failed admission gates

### Activity Reason Codes
- `NO_ACTIVITY_365D` - No usage in past year
- `HAS_RECENT_ACTIVITY` - Active usage detected
- `DISCOVERY_ONLY` - Only seen in discovery, no other signals

---

## Success Metrics

Target accuracy levels:
- **Shadow IT detection**: 99.5%+ (critical - don't miss security risks)
- **Zombie detection**: 97.5%+ (important - catch cost waste)
- **Combined accuracy**: 99%+ across all test tenants

Current performance (Jan 2026):
- HelixSystems: 99.8% combined
- CyberWorks: 99.3% combined  
- InfoWorks: 99.4% combined
