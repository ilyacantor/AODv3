# KEY_NORMALIZATION_MISMATCH Fix - State & Learnings

**Date:** January 10, 2026  
**Status:** Rolling back failed fix attempts

---

## Problem Statement

AOD Discover has KEY_NORMALIZATION_MISMATCH reconciliation errors where:
- Farm expects assets by governance-plane domains (IdP/CMDB)
- AOD keys assets by discovery domains
- Farm can't find 13 zombie assets and 3 shadow IT assets

**Assessment Numbers (before fix attempts):**
- Zombies: 37 expected, ~24 matched, 13 missed
- Shadows: 72 expected, 69 matched, 3 missed

---

## Failed Fix Attempts

### Attempt 1: Modify `_resolve_domain_key()` 
**File:** `src/aod/pipeline/aod_agent_reconcile.py`

**Change:** Refactored to process ALL domains in `identifiers.domains`, freezing primary key from `domain[0]`

**Result:** REGRESSION
- Helped 2 zombies (corespace.ai, rapiddesk.com)
- Broke 5 previously-matching zombies (fasthub.dev, fasthub.co, ultraflow.dev, smarthub.co, flexsuite.dev)
- Net: -3 zombies

**Why it failed:** Changed the primary key selection logic. If `domains[0]` differs from what the old logic selected, the emitted key changes and Farm can't find it.

### Attempt 2: Modify `emit_actual_results()`
**File:** `src/aod/pipeline/aod_agent_reconcile.py`

**Change:** Added all `alias_keys` to `zombie_actual`/`shadow_actual`/`parked_actual` lists

**Result:** NO IMPROVEMENT
- Still 16 missed zombies, 3 missed shadows
- The 5 regressed zombies remained broken

**Why it failed:** `alias_keys` was empty because governance domains never made it into `identifiers.domains` in the first place. Adding empty aliases to output lists does nothing.

---

## Root Cause Analysis

### The Fundamental Mistake
Both fixes targeted downstream layers (output/key selection) without verifying upstream data flow.

### Data Flow (Expected vs Actual)

**Expected:**
```
IdP/CMDB Plane Records → identifiers.domains → _resolve_domain_key → alias_keys → output lists
```

**Actual:**
```
IdP/CMDB Plane Records → [STUCK IN PLANE-SPECIFIC FIELDS] ✗
                         identifiers.domains only has DISCOVERY domains
                         → _resolve_domain_key sees only discovery domains
                         → alias_keys has no governance domains
                         → output lists can't include what doesn't exist
```

### Evidence
- Assessment shows only 20 zombie keys emitted vs 37 expected
- If governance domains were in alias_keys, output would be larger (primary + aliases)
- Flat count proves governance domains never reached alias_keys

---

## What Needs to Happen

### 1. Trace Real Data First
Pick a specific missed zombie (e.g., `fasthub.dev`) and trace:
- Where is the governance domain stored in the plane record?
- What field? (`entity.domain`? `raw_data.external_ref`?)
- Does it get extracted during indexing?
- Does it reach correlation?
- At what point is it dropped?

### 2. Fix at the Right Layer
The fix must happen where domains are LOST:
- Likely during identifier aggregation in `derived_classifications.py` or `build_plane_indexes.py`
- Governance domains need to be collected into `identifiers.domains` during asset construction
- NOT downstream in emit/key selection

### 3. Preserve Key Stability
Any fix must NOT change primary key selection for existing assets. The regression happened because the key selection logic changed.

### 4. Test Strategy
After any change:
1. First verify existing matches STILL work (no regression)
2. Then check if new matches are found
3. If existing matches break, stop and analyze

---

## Files to Investigate

1. **`src/aod/pipeline/derived_classifications.py`** - Where identifiers are built
2. **`src/aod/pipeline/build_plane_indexes.py`** - Where plane records are indexed
3. **`src/aod/pipeline/admission.py`** - Where correlation happens
4. **`src/aod/pipeline/aod_agent_reconcile.py`** - Output layer (already investigated)

---

## Key Questions to Answer

1. Where exactly are governance domains stored in plane records?
2. What code path should extract them into `identifiers.domains`?
3. Is there existing code that's supposed to do this but isn't working?
4. Or does this extraction logic need to be added?

---

## Specific Assets to Trace

**Regressed zombies (were matching, now broken):**
- fasthub.dev
- fasthub.co
- ultraflow.dev
- smarthub.co
- flexsuite.dev

**Missed shadows (unchanged):**
- amazon.com
- tiktok.com
- workers.dev

---

## After Rollback

1. Verify the 5 regressed zombies are matching again
2. Trace a single missed zombie's data flow end-to-end
3. Identify the exact function/line where governance domains are dropped
4. Plan fix at that specific location
5. Test incrementally with regression checks
