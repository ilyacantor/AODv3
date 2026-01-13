# Root Cause Analysis - Final Report

## Reconciliation Run: `run_e5afffb1c9c8`
**Date:** 2026-01-13T18:00:20
**Shadow FPs:** 10 total

---

## Issue 1: Vendor Governance (4 FPs) ✓ FIX CONFIRMED WORKING

**Affected Assets:**
- teamdesk.net
- corelabs.tech
- teamsuite.cloud
- teamsuite.ai

**Root Cause:**
IdP records have no `domain` fields, only names. My fix infers domains from IdP names via VENDOR_TO_DOMAIN mapping.

**Test Results (Re-verified with deployed code):**
```
✓ teamdesk.net: _extract_idp_domain("TEAMDESK") → "teamdesk.net" → MATCH → idp_governance_aligned=TRUE
✓ corelabs.tech: _extract_idp_domain("Corelabs") → "corelabs.tech" → MATCH → idp_governance_aligned=TRUE
✓ teamsuite.cloud: _extract_idp_domain("Teamsuite") → "teamsuite.cloud" → MATCH → idp_governance_aligned=TRUE
✓ teamsuite.ai: _extract_idp_domain("Teamsuite") → "teamsuite.cloud" → vendor match → idp_governance_aligned=TRUE
```

**Status:** ✓ ALL TESTS PASS with deployed aod package

**Reconciliation Shows:**
- `HAS_IDP` but also `SHADOW_CLASSIFICATION` + `FINANCIAL_ANCHOR_GOVERNANCE_GAP`
- This means `idp_governance_aligned = FALSE` in the AOD run

**Conclusion:**
The fix works in my tests but NOT in the actual AOD run (`run_e5afffb1c9c8`).

**Possible Reasons:**
1. AOD run `run_e5afffb1c9c8` executed BEFORE code was deployed
2. Different code path being used in production AOD pipeline
3. Python import/module caching issue in production environment
4. Different version of aod package installed

---

## Issue 2: Finance Correlation (3 FPs) - SEPARATE ISSUE

**Affected Assets:**
- rapidio.ai
- fastlabs.ai  
- easysync.ai

**Root Cause:**
Finance token-based correlation failing.

**Evidence:**
```
rapidio.ai → token 'rapidio' → matches vendor 'Rapidio Inc' (token 'rapidio') ✓
fastlabs.ai → token 'fastlabs' → DOESN'T match vendor 'Fastlabs-Inc' (token 'fastlabsinc') ✗
easysync.ai → token 'easysync' → matches vendor 'easysync inc' (token 'easysync') ✓
```

**Expected:** 2 out of 3 should correlate to finance
**Actual:** AOD shows `NO_FINANCE` for all 3

**Token Blocking Check:** ✓ PASSED (not blocked by generic token filter)

**Status:** Finance correlation logic exists (lines 1089-1129 in correlate_entities.py) but isn't working in production.

---

## Issue 3: Policy Differences (3 FPs) - NOT A BUG

Farm rejects discovery-only entities, AOD admits them. This is expected behavior.

---

## Critical Question

**If all my tests pass with the deployed aod package, why does production AOD run still fail?**

Possible scenarios:
1. **Timing:** Run `run_e5afffb1c9c8` executed before latest code deployed
2. **Different pipeline:** Production uses different entry point that bypasses my fixes
3. **Module caching:** Production environment has stale .pyc files
4. **Different snapshot:** Production running against different data than cyberhub_snapshot.json

**Recommendation:** Need to verify that `run_e5afffb1c9c8` is using the code from branch `claude/analyze-key-normalization-X7VDd` (commit b1cd6ad or later).

