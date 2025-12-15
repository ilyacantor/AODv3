# Zombie v0 - Experimental Debug Lane

This is a completely isolated experimental module for zombie classification.

## Purpose

Zombie v0 exists only to answer:
"Given a run_id and X days, which assets are zombies?"

- No shadows
- No reconciliation
- No scoring
- No ML
- No reuse of existing AOD logic

## API

**Endpoint:** `GET /experimental/zombie_v0/zombies`

**Query Parameters:**
- `run_id` (required) - The run ID to analyze
- `window_days` (required) - Activity window in days

**Response:**
```json
{
  "run_id": "run_123",
  "window_days": 90,
  "results": [
    {
      "asset_id": "hipchatcom",
      "exists_in_sor": true,
      "activity_in_window": false,
      "zombie": true,
      "last_activity_observed_at": null,
      "reason": "Exists in CMDB; no activity observed in last 90 days."
    }
  ]
}
```

## Logic

**Definitions:**
- **Exists** = asset appears in any system of record: CMDB, Billing, IdP, Cloud inventory
- **Activity** = any `observed_at` >= now - window_days

**Zombie rule (binary):**
```
zombie = exists AND NOT activity
```

## Isolation

This module:
- Does NOT modify any existing AOD code
- Does NOT reuse existing zombie logic
- Does NOT write to the database (read-only)
- Does NOT emit data to Farm

## Files

- `api.py` - FastAPI router with the endpoint
- `logic.py` - Classification logic written from scratch
- `types.py` - Pydantic models for the response
- `README.md` - This file
