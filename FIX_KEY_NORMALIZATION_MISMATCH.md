# Fix for KEY_NORMALIZATION_MISMATCH: Use Canonical Keys for Rejections

## Problem

Rejections use internal entity IDs (`entity:obs_12345`) instead of canonical domain keys (`dropboxusercontent.io`), causing Farm reconciliation mismatches.

## Root Cause Location

**File:** `src/aod/pipeline/pipeline_executor.py`
**Lines:** 202, 217

```python
# CURRENT BUG:
rejections_batch.append((
    rejection_id, run_id,
    candidate.entity_id,      # ← "entity:obs_12345"
    candidate.original_name,  # ← "Dropbox User Activity"
    ...
))
```

## Solution

Use the same canonical key extraction logic as admitted assets (from `aod_agent_reconcile.py:_extract_raw_domain()`):

```python
def _get_rejection_key(candidate: CandidateEntity) -> str:
    """
    Extract canonical rejection key matching Farm's expectations.
    Uses same logic as _extract_raw_domain() for admitted assets.
    """
    # Priority 1: Domain (preserve subdomains for host-level granularity)
    if candidate.domain:
        return candidate.domain.lower().strip()

    # Priority 2: Name if it looks like a domain
    name = candidate.original_name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2:
            tld = parts[-1]
            if tld in ("com", "net", "org", "io", "co", "app", "dev", "us", "cloud"):
                return name

    # Priority 3: Vendor lookup (fallback)
    if candidate.vendor and candidate.vendor.lower() not in ("unknown", "", "none"):
        from .aod_agent_reconcile import VENDOR_TO_DOMAIN
        vendor_key = candidate.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]

    # Fallback: Normalized name
    import re
    return re.sub(r'[^a-z0-9]', '', name.lower())
```

## Implementation

**File:** `src/aod/pipeline/pipeline_executor.py`

### Step 1: Add helper function at top of file

```python
from .aod_agent_reconcile import VENDOR_TO_DOMAIN

def _get_rejection_key(candidate: CandidateEntity) -> str:
    """Extract canonical rejection key matching Farm's expectations"""
    if candidate.domain:
        return candidate.domain.lower().strip()

    name = candidate.original_name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and parts[-1] in ("com", "net", "org", "io", "co", "app", "dev", "us", "cloud"):
            return name

    if candidate.vendor and candidate.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = candidate.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]

    import re
    return re.sub(r'[^a-z0-9]', '', name.lower())
```

### Step 2: Update rejection creation (lines 200-207)

```python
# BEFORE:
rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
rejections_batch.append((
    rejection_id, run_id, candidate.entity_id, candidate.original_name,
    "no_correlation", "Entity not found in correlation results",
    json.dumps({"source": candidate.source, "domain": candidate.domain}),
    started_at.isoformat()
))

# AFTER:
rejection_key = _get_rejection_key(candidate)  # ← Use canonical key!
rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
rejections_batch.append((
    rejection_id, run_id,
    rejection_key,              # ← entity_key = "dropboxusercontent.io"
    rejection_key,              # ← entity_name = "dropboxusercontent.io"
    "no_correlation", "Entity not found in correlation results",
    json.dumps({"source": candidate.source, "domain": candidate.domain, "original_name": candidate.original_name}),
    started_at.isoformat()
))
```

### Step 3: Update admission rejection (lines 215-226)

```python
# BEFORE:
rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
rejections_batch.append((
    rejection_id, run_id, candidate.entity_id, candidate.original_name,
    "admission_failed", admission_result.rejection_reason or "No admission criteria satisfied",
    json.dumps({
        "idp_status": correlation.idp.status.value,
        "cmdb_status": correlation.cmdb.status.value,
        "cloud_status": correlation.cloud.status.value,
        "finance_status": correlation.finance.status.value
    }),
    started_at.isoformat()
))

# AFTER:
rejection_key = _get_rejection_key(candidate)  # ← Use canonical key!
rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
rejections_batch.append((
    rejection_id, run_id,
    rejection_key,              # ← entity_key = "dropboxusercontent.io"
    rejection_key,              # ← entity_name = "dropboxusercontent.io"
    "admission_failed", admission_result.rejection_reason or "No admission criteria satisfied",
    json.dumps({
        "idp_status": correlation.idp.status.value,
        "cmdb_status": correlation.cmdb.status.value,
        "cloud_status": correlation.cloud.status.value,
        "finance_status": correlation.finance.status.value,
        "original_name": candidate.original_name,  # ← Preserve for debugging
        "original_entity_id": candidate.entity_id   # ← Preserve for debugging
    }),
    started_at.isoformat()
))
```

## Expected Outcome

**Before Fix:**
```json
{
  "entity_key": "entity:obs_12345",
  "entity_name": "Dropbox User Activity",
  "reason_code": "admission_failed"
}
```
→ Farm expects `dropboxusercontent.io`, AOD emits nothing → **KEY_NORMALIZATION_MISMATCH**

**After Fix:**
```json
{
  "entity_key": "dropboxusercontent.io",
  "entity_name": "dropboxusercontent.io",
  "reason_code": "admission_failed",
  "evidence_summary": {
    "original_name": "Dropbox User Activity",
    "original_entity_id": "entity:obs_12345"
  }
}
```
→ Farm expects `dropboxusercontent.io`, AOD emits `"rejected"` with reason → **Match!** ✅

## Verification

After implementing, check reconciliation output:

```bash
curl http://localhost:8000/api/runs/{run_id}/reconcile-payload
```

Should now show rejected assets with canonical keys matching Farm's expectations.

## Answer to User's Question

**Option B is already implemented!** The infrastructure exists to include rejected assets in reconciliation. The bug was that rejections used wrong keys.

**Fix:** Use canonical domain keys for rejections (same as admitted assets).

**Don't need Option A** (lowering threshold to 1 source) - rejections will now appear correctly in reconciliation with proper "rejected" status.
