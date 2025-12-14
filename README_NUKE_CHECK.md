# Nuke Prevention Check

A fast, repeatable sanity check that verifies the AOD discovery pipeline works correctly.

## Quick Start

```bash
python scripts/nuke_check.py
```

## What It Does

The Nuke Prevention Check runs a series of automated tests to verify the AOD pipeline is functioning correctly:

1. **Project Detection** - Confirms this is an AOD project
2. **Environment Check** - Verifies FARM_URL is configured
3. **Server Health** - Confirms AOD server is running
4. **Farm Connectivity** - Lists tenants and snapshots from Farm
5. **Discovery Run** - Executes a full discovery pipeline
6. **Status Validation** - Ensures run returns valid status codes
7. **Determinism Check** - Runs the same snapshot twice and compares outputs

## Requirements

- AOD server running on port 5000
- `FARM_URL` environment variable set
- At least one tenant with snapshots in Farm

## Output Format

### Success
```
============================================================
NUKE CHECK: PASS
Project: AOD
Timestamp: 2025-01-15T10:30:00Z

Key results:
  - [PASS] FARM_URL is configured: https://farm.example.com...
  - [PASS] AOD server is healthy
  - [PASS] Found 3 tenant(s), using: acme-corp
  - [PASS] Found 10 snapshot(s), using: snap_abc123...
  - [PASS] Run 1: status=COMPLETED_WITH_RESULTS, assets=42, findings=5
  - [PASS] Run 2: status=COMPLETED_WITH_RESULTS, assets=42, findings=5
  - [PASS] Determinism check passed: both runs produced identical outputs
  - [INFO] Completed in 15.3 seconds
============================================================
```

### Failure
```
============================================================
NUKE CHECK: FAIL
Project: AOD
Timestamp: 2025-01-15T10:30:00Z

Key results:
  - [PASS] FARM_URL is configured
  - [FAIL] Cannot connect to AOD server

What failed: Cannot connect to AOD server
Likely cause: The AOD server is not running or not reachable
What to do: Start the server with: python -m uvicorn src.main:app --host 0.0.0.0 --port 5000
============================================================
```

## Suggested Cadence

- **Daily** - Run as part of daily health checks
- **Before merge/deploy** - Run before merging PRs or deploying to production
- **After dependency updates** - Verify pipeline still works after package updates

## Exit Codes

- `0` - All checks passed
- `1` - One or more checks failed

## Checks Performed

| Check | Description |
|-------|-------------|
| FARM_URL | Environment variable must be set |
| Server Health | AOD /api/health returns 200 |
| Tenant List | Farm has at least one tenant |
| Snapshot List | Tenant has at least one snapshot |
| Discovery Run | Pipeline completes with valid status |
| Status Codes | Must be UPSTREAM_ERROR, INVALID_SNAPSHOT, COMPLETED_NO_ASSETS, or COMPLETED_WITH_RESULTS |
| Determinism | Two runs produce identical counts and asset lists |

## Troubleshooting

### "FARM_URL environment variable is not set"
```bash
export FARM_URL=https://your-farm-server.example.com
```

### "Cannot connect to AOD server"
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 5000
```

### "No tenants found in Farm"
Ensure your Farm server has at least one tenant with generated snapshots.

### "Determinism check failed"
This indicates the pipeline is producing different outputs for the same input. Check for:
- Random UUIDs generated during the run
- Timestamps used in comparisons
- Unstable sorting in the pipeline
