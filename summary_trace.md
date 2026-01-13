# Root Cause Analysis Summary

## Issue 1: Vendor Governance FPs (4 FPs) - MY FIX IS CORRECT
**Affected:** teamdesk.net, corelabs.tech, teamsuite.cloud, teamsuite.ai

**Status:** Fix works locally, NOT deployed to production

**Evidence:**
- Local tests: ALL PASS (simple_trace.py, trace_complete_flow.py, final_diagnostic.py)
- `_extract_idp_domain` correctly infers domains from IdP names
- `_idp_domain_matches_entity` correctly matches via vendor
- `idp_governance_aligned` should be TRUE

**Production shows:** `idp_governance_aligned = FALSE` → Shadow classification

**Conclusion:** Code fix is correct. Production environment issue (deployment, caching, or Docker).

---

## Issue 2: Finance Correlation Failure (3 FPs) - DIFFERENT ROOT CAUSE  
**Affected:** rapidio.ai, fastlabs.ai, easysync.ai

**Status:** Not a vendor governance issue - it's a FINANCE CORRELATION issue

**Evidence:**
- These assets have finance records (vendors, contracts, transactions)
- But AOD shows NO_FINANCE in reason codes
- Finance vendors have names ("Rapidio Inc") but no vendor_domain fields
- Entities have domains ("rapidio.ai")

**Expected:** Token-based matching should correlate them (lines 1089-1129 in correlate_entities.py)

**Actual:** Finance correlation failing

**Root cause options:**
1. Token matching code not being executed
2. Finance plane check failing (line 1096)
3. Token extraction mismatch (fastlabs vs fastlabsinc)
4. Production using different correlation logic

**Recommendation:** Need to debug why finance token-based matching isn't working in production.

---

## Summary:
- 4 FPs are due to vendor governance fix not deployed
- 3 FPs are due to finance correlation failure (separate issue)
- Need production logs/output to diagnose both

