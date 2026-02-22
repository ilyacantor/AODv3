# Triage Recording Fix

## Problem Summary

Triage actions were not being recorded/reported correctly:
- Actions applied in the triage workflow weren't reflected in the catalog
- Stale actions from different item_types were appearing
- Same asset could have multiple conflicting triage records in one run

## Root Cause

The database allowed **multiple triage action records per asset per run** because the unique constraint was `(run_id, item_id, item_type)` instead of `(run_id, item_id)`.

This meant:
- Triaging an asset as "shadow" created one record with `item_type='shadow'`
- Later triaging the same asset as "zombie" created a **separate** record with `item_type='zombie'`
- The catalog view had broken priority logic that showed stale actions instead of recent ones
- The triage UI couldn't find actions when the asset moved between sections

## The Fix

### 1. Database Schema (src/aod/db/schema.py)
- Added `UNIQUE(run_id, item_id)` constraint to `triage_actions` table
- Added automatic migration to clean up existing duplicates on startup

### 2. Database Operations (src/aod/db/operations/triage.py)
- Changed `save_triage_action` to check for existing actions by `(run_id, item_id)` only
- When updating, also updates `item_type` in case asset moved to different section
- This ensures ONE action per asset per run, regardless of which triage section it appears in

### 3. Catalog View (src/aod/api/routes/catalog.py)
- Removed broken priority-based deduplication logic
- Simplified to direct mapping since UNIQUE constraint ensures no duplicates
- Added 'blocking' and 'judgment' to recognized item_types

### 4. Frontend JavaScript (static/js/app.js)
- Simplified `triageActionsMap` to use `assetId` as key instead of `${itemType}:${assetId}`
- Updated all lookups to use simpler key format
- Ensures UI correctly reflects actions regardless of which section asset appears in

## How to Apply

### Step 1: Run Migration (Optional but Recommended)

Before restarting the server, clean up any existing duplicate triage actions:

```bash
python migrate_triage_duplicates.py
```

This script:
- Finds all duplicate triage actions (same run_id and item_id)
- Keeps the most recent action (by updated_at timestamp)
- Deletes older duplicates

**Note:** The schema will also auto-migrate on next startup, so this step is optional.

### Step 2: Restart Server

The schema migration runs automatically on startup, but manually running the migration script first gives you visibility into what's being cleaned up.

```bash
python src/aod/main.py
```

### Step 3: Verify Fix (Optional)

Run the test script to verify everything works correctly:

```bash
python test_triage_fix.py
```

This tests:
- Creating a triage action works
- Trying to create a duplicate fails (UNIQUE constraint enforced)
- Updating an existing action works
- No duplicates exist in the database

## Expected Behavior After Fix

### Triage Workflow
1. Operator takes action on asset in any section (firewall, risk, hygiene)
2. **ONE** triage record is created/updated for that asset in that run
3. If operator later takes a different action on the same asset, the existing record is **updated**
4. Actions immediately reflect in the UI

### Catalog View
1. Shows the **most recent** triage action for each asset
2. No stale actions from different item_types
3. Triage badges accurately reflect current state

### Across Runs
- Each new discovery run starts fresh
- Triage actions are run-scoped (not carried forward)
- No cross-contamination between runs

## Files Changed

- `src/aod/db/schema.py` - Added UNIQUE constraint and auto-migration
- `src/aod/db/operations/triage.py` - Updated save/lookup logic
- `src/aod/api/routes/catalog.py` - Removed broken deduplication
- `static/js/app.js` - Simplified action mapping
- `migrate_triage_duplicates.py` - Manual migration script (NEW)
- `test_triage_fix.py` - Verification tests (NEW)

## Technical Details

### Database Constraint
```sql
CREATE TABLE triage_actions (
    ...
    UNIQUE(run_id, item_id)  -- One action per asset per run
)
```

### Key Insight
`item_type` is **informational metadata** (which section the asset appeared in), not part of the identity. An asset's triage decision should be singular per run, regardless of how many sections it appears in.

If an asset is both "shadow" (no governance) and "blocking" (has identity gap), the operator still makes **one** decision: sanction, ban, defer, etc. That decision applies to the asset as a whole, not to individual classifications.
