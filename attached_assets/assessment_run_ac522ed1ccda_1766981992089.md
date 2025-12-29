# Reconciliation Assessment Report

**AOD Run:** `run_ac522ed1ccda`
**Reconciliation ID:** `8e42099f-2e01-4811-8231-2aa1e041dd29`
**Snapshot ID:** `2ed4c6c6-cc91-4cd9-a0b2-7244d016f62a`
**Tenant:** `NetCorp-4S6E`
**Generated:** 2025-12-29T04:18:48.025134Z

---

## Executive Summary

**Overall Status:** FAIL
**Verdict:** NEEDS WORK - classification missed 42/56
**Combined Accuracy:** 71.2%

### Summary Table

| Category | Farm Expected | AOD Found | Matched | Missed | FP |
|----------|---------------|-----------|---------|--------|-----|
| Shadows | 53 | 13 | 14 | 39 | 0 |
| Zombies | 3 | 8 | 0 | 3 | 8 |

### Lifecycle Funnel

- **Gross Observations:** 1503
- **Unique Assets:** 172
- **Rejected (not admitted):** 80
- **Admitted:** 92
- **Cataloged (final):** 92

---

## Classification Analysis

### Matched Shadows (Correctly Identified)

**14 assets correctly identified as Shadow IT**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| airtable.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| fastlabs.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| dropbox.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | FINANCIAL_ANCHOR_GOVERNANCE_GAP, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CLOUD | - |
| netpoint.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| canva.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | FINANCIAL_ANCHOR_GOVERNANCE_GAP, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CLOUD | UNGOVERNED_ACTIVE |
| primepoint.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| box.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | FINANCIAL_ANCHOR_GOVERNANCE_GAP, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CLOUD | UNGOVERNED_ACTIVE |
| evernote.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| monday.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| syncapp.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| loom.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | FINANCIAL_ANCHOR_GOVERNANCE_GAP, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CLOUD | UNGOVERNED_ACTIVE |
| coresuite.co | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| rapidify.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |
| webex.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, NO_CMDB | UNGOVERNED_ACTIVE |

### Missed Shadows (False Negatives)

**39 assets missed by AOD - should have been Shadow IT**

#### `tiktok.com`

**Headline:** AOD missed tiktok.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for tiktok.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, RECENT_ACTIVITY`

#### `maxflow.io`

**Headline:** AOD missed maxflow.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for maxflow.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `asana.com`

**Headline:** AOD missed asana.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for asana.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `fastio.ai`

**Headline:** AOD missed fastio.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for fastio.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowify.app`

**Headline:** AOD missed flowify.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flowify.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `zoom.us`

**Headline:** AOD missed zoom.us as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for zoom.us but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncspace.org`

**Headline:** AOD missed syncspace.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncspace.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `protech.org`

**Headline:** AOD missed protech.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for protech.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `pagerduty.com`

**Headline:** AOD missed pagerduty.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for pagerduty.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `google.com`

**Headline:** AOD missed google.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for google.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `surveymonkey.com`

**Headline:** AOD missed surveymonkey.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for surveymonkey.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `opensuite.app`

**Headline:** AOD missed opensuite.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for opensuite.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linksuite.com`

**Headline:** AOD missed linksuite.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for linksuite.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `splunk.com`

**Headline:** AOD missed splunk.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for splunk.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `coreworks.io`

**Headline:** AOD missed coreworks.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for coreworks.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workflow.cloud`

**Headline:** AOD missed workflow.cloud as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for workflow.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linkfy.cloud`

**Headline:** AOD missed linkfy.cloud as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for linkfy.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `docusign.com`

**Headline:** AOD missed docusign.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for docusign.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `grammarly.com`

**Headline:** AOD missed grammarly.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for grammarly.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, RECENT_ACTIVITY`

#### `calendly.com`

**Headline:** AOD missed calendly.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for calendly.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, RECENT_ACTIVITY`

#### `snowflakecomputing.com`

**Headline:** AOD missed snowflakecomputing.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for snowflakecomputing.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `coresync.co`

**Headline:** AOD missed coresync.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for coresync.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `typeform.com`

**Headline:** AOD missed typeform.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for typeform.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, RECENT_ACTIVITY`

#### `linkapp.cloud`

**Headline:** AOD missed linkapp.cloud as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for linkapp.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `cloudpoint.dev`

**Headline:** AOD missed cloudpoint.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for cloudpoint.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `netcorp-4s6e.com`

**Headline:** AOD missed netcorp-4s6e.com as shadow IT

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `None`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, RECENT_ACTIVITY`

#### `easydesk.io`

**Headline:** AOD missed easydesk.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for easydesk.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultraforce.com`

**Headline:** AOD missed ultraforce.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for ultraforce.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowbase.ai`

**Headline:** AOD missed flowbase.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for flowbase.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workday.com`

**Headline:** AOD missed workday.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for workday.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `clickup.com`

**Headline:** AOD missed clickup.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for clickup.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `cloudpoint.co`

**Headline:** AOD missed cloudpoint.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for cloudpoint.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartpoint.co`

**Headline:** AOD missed smartpoint.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for smartpoint.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datadoghq.com`

**Headline:** AOD missed datadoghq.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for datadoghq.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `easyapp.net`

**Headline:** AOD missed easyapp.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for easyapp.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowbase.co`

**Headline:** AOD missed flowbase.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for flowbase.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubspot.com`

**Headline:** AOD missed hubspot.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubspot.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartsync.cloud`

**Headline:** AOD missed smartsync.cloud as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for smartsync.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `primeworks.ai`

**Headline:** AOD missed primeworks.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for primeworks.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

### Missed Zombies (False Negatives)

**3 assets missed by AOD - should have been Zombie**

#### `yammer.com`

**Headline:** AOD missed yammer.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for yammer.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY, GOVERNED_VIA_VENDOR`

#### `primesoft.io`

**Headline:** AOD missed primesoft.io as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for primesoft.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, STALE_ACTIVITY`

#### `zoom-legacy.com`

**Headline:** AOD missed zoom-legacy.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for zoom-legacy.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

### False Positive Zombies

**8 assets incorrectly classified as Zombie by AOD**

#### Farm Classification: `parked` (8 assets)

**`flexbase.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`linkify.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`pivotaltracker.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`cloudcloud.co`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`prosuite.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`flowdock.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`smartworks.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

**`basecamp.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, ANCHORED, DISCOVERY_SOURCE_COUNT_LT_2, STALE_ACTIVITY, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, HAS_IDP, NO_CLOUD, ZOMBIE_CLASSIFICATION`

---

## Admission Analysis

### Admission Metrics

- **Total Assets:** 162
- **Matched:** 147
- **Missed:** 15
- **False Positives:** 26
- **Accuracy:** 90.7%

---

## Root Cause Analysis Summary

| RCA Hint | Count |
|----------|-------|
| KEY_NORMALIZATION_MISMATCH | 41 |
| FP_FROM_PARKED | 8 |
| UNKNOWN | 1 |

---

## Recommendations

- **Key Normalization:** AOD has evidence for some assets but is not using the expected canonical keys. Review key normalization logic.
- **Shadow Detection:** 39 expected shadows not found. Check shadow classification rules.
- **Zombie Detection:** 3 expected zombies not found. Check zombie classification rules.

---

*Generated by AOS Farm Assessment Engine*