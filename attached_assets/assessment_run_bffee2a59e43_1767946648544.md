# Reconciliation Assessment Report

**AOD Run:** `run_bffee2a59e43`
**Reconciliation ID:** `c66f3050-5330-4a87-b1b0-76f6548efed0`
**Snapshot ID:** `65987a5a-2555-48ee-a283-96c7ed4f07c5`
**Tenant:** `DataDynamics-V4S5`
**Generated:** 2026-01-09T08:16:12.131517Z

---

## Executive Summary

**Overall Status:** WARN
**Verdict:** SOME IMPROVEMENT NEEDED - classification 91/109
**Combined Accuracy:** 97.2%

### Summary Table

| Category | Farm Expected | AOD Found | Matched | Missed | FP |
|----------|---------------|-----------|---------|--------|-----|
| Shadows | 72 | 74 | 68 | 4 | 5 |
| Zombies | 37 | 23 | 23 | 14 | 0 |

### Lifecycle Funnel

- **Gross Observations:** 3347
- **Unique Assets:** 1298
- **Rejected (not admitted):** 707
- **Admitted:** 591
- **Cataloged (final):** 591

---

## Classification Analysis

### Matched Shadows (Correctly Identified)

**68 assets correctly identified as Shadow IT**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| flowcloud.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| hubbox.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| ultrabase.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| datahub.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| proflow.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| workbox.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| airtable.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| rapidsync.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| rapidbase.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| flowpoint.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| maxcloud.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| okta.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| miro.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| smartworks.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| easyspace.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| cloudflareinsights.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| loom.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| datasuite.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| datapoint.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| flowspace.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| primedesk.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| cloudworks.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| typeform.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| hubsoft.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| clickup.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| maxsuite.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| openapp.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| maxflow.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| amazon.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| flexhub.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| opencloud.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| canva.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| ultrafy.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flowify.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| zapier.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flowworks.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| easybox.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flowify.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| hubpoint.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| snowflakecomputing.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| easyfy.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| opensync.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| easyspace.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| evernote.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| opencloud.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| rapidbase.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| proflow.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| dataspace.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flowflow.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| dropbox.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| dataify.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| flexspace.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| openbox.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| calendly.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| netbase.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| primetech.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flowbase.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| primefy.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| smartsoft.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| primeify.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| datatech.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| monday.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| openforce.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| flexspace.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| worksync.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |
| surveymonkey.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| flexfy.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_ONGOING_FINANCE, NO_IDP, NO_CMDB | UNGOVERNED_ACTIVE |
| synctech.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP | UNGOVERNED_ACTIVE |

### Missed Shadows (False Negatives)

**4 assets missed by AOD - should have been Shadow IT**

#### `workers.dev`

**Headline:** AOD missed workers.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for workers.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

#### `typekit.net`

**Headline:** AOD missed typekit.net as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

#### `tiktok.com`

**Headline:** AOD missed tiktok.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for tiktok.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

#### `cloudfront.net`

**Headline:** AOD missed cloudfront.net as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, HAS_CLOUD, RECENT_ACTIVITY`

### False Positive Shadows

**5 assets incorrectly classified as Shadow IT by AOD**

#### Farm Classification: `clean` (3 assets)

**`microsoft.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB, HAS_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, DISCOVERY_SOURCE_COUNT_GE_2, ANCHORED, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`
- **In Farm only:** `HAS_SECURITY_ATTESTATION, GOVERNED`
- **In AOD only:** `FINANCIALLY_ANCHORED, NOT_ANCHORED, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, ANCHORED`

**`datadynamics-v4s5.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED, RECENT_ACTIVITY`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`
- **In Farm only:** `HAS_IDP, NO_SECURITY_ATTESTATION, GOVERNED, HAS_CMDB`
- **In AOD only:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION`

**`salesforceliveagent.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY, GOVERNED_VIA_VENDOR`
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`
- **In Farm only:** `HAS_IDP, HAS_FINANCE, HAS_CMDB, HAS_ONGOING_FINANCE, GOVERNED_VIA_VENDOR, GOVERNED, HAS_SECURITY_ATTESTATION`
- **In AOD only:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION`

#### Farm Classification: `unknown` (1 assets)

**`adobe.com`**

- **Farm Reason Codes:** ``
- **AOD Reason Codes:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`
- **In AOD only:** `NO_ONGOING_FINANCE, NOT_ANCHORED, NO_IDP, NO_CMDB, NO_FINANCE, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`

#### Farm Classification: `not-admitted` (1 assets)

**`netbox.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_ONGOING_FINANCE, NO_IDP, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, DISCOVERY_SOURCE_COUNT_GE_2, ANCHORED, SHADOW_CLASSIFICATION, RECENT_ACTIVITY, HAS_DISCOVERY`
- **In Farm only:** `UNGOVERNED, NO_SECURITY_ATTESTATION`
- **In AOD only:** `FINANCIALLY_ANCHORED, DISCOVERY_SOURCE_COUNT_GE_2, SHADOW_CLASSIFICATION, ANCHORED, FINANCIAL_ANCHOR_GOVERNANCE_GAP`

### Matched Zombies (Correctly Identified)

**23 assets correctly identified as Zombie**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| maxfy.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| cloudapp.dev | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| rapiddesk.com | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, DISCOVERY_SOURCE_COUNT_LT_2, HAS_FINANCE, FINANCIALLY_ANCHORED | STALE_NO_RECENT_USE |
| linktech.org | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| ultraflow.dev | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, DISCOVERY_SOURCE_COUNT_LT_2, FINANCIALLY_ANCHORED, HAS_FINANCE | STALE_NO_RECENT_USE |
| easyworks.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| fastspace.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, DISCOVERY_SOURCE_COUNT_LT_2, FINANCIALLY_ANCHORED, HAS_FINANCE | STALE_NO_RECENT_USE |
| opensoft.org | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| syncdesk.tech | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| cloudcloud.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| hipchat.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| flowly.app | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| corespace.ai | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| linkly.tech | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| flexbase.org | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| flexflow.com | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| cloudcloud.ai | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| flexflow.org | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |
| linkio.org | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| workcloud.cloud | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| yammer.com | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| openio.ai | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_LT_2, FINANCIALLY_ANCHORED, HAS_FINANCE, HAS_CMDB | STALE_NO_RECENT_USE |
| flowly.co | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_IDP, HAS_FINANCE, FINANCIALLY_ANCHORED, ZOMBIE_CLASSIFICATION | STALE_NO_RECENT_USE |

### Missed Zombies (False Negatives)

**14 assets missed by AOD - should have been Zombie**

#### `probase.com`

**Headline:** AOD missed probase.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `worktech.co`

**Headline:** AOD missed worktech.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for worktech.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `probase.org`

**Headline:** AOD missed probase.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `protech.com`

**Headline:** AOD missed protech.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for protech.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fasthub.dev`

**Headline:** AOD missed fasthub.dev as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fasthub.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flexsuite.dev`

**Headline:** AOD missed flexsuite.dev as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flexsuite.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `ultralabs.co`

**Headline:** AOD missed ultralabs.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for ultralabs.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `smarthub.co`

**Headline:** AOD missed smarthub.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for smarthub.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fasthub.co`

**Headline:** AOD missed fasthub.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fasthub.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `probase.ai`

**Headline:** AOD missed probase.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `coreforce.com`

**Headline:** AOD missed coreforce.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for coreforce.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `ultralabs.ai`

**Headline:** AOD missed ultralabs.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for ultralabs.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `workify.io`

**Headline:** AOD missed workify.io as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for workify.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `zoom-legacy.com`

**Headline:** AOD missed zoom-legacy.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for zoom-legacy.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

---

## Admission Analysis

### Admission Metrics

- **Total Assets:** 1298
- **Matched:** 1281
- **Missed:** 17
- **False Positives:** 19
- **Accuracy:** 98.7%

### Cataloged Missed by AOD

**14 assets should have been cataloged but weren't**

| Asset | Farm Classification |
|-------|---------------------|
| pivotaltracker.com | admitted |
| tiktok.com | admitted |
| googleusercontent.com | admitted |
| coresuite.co | admitted |
| basecamp.com | admitted |
| workers.dev | admitted |
| cloudfront.net | admitted |
| coreflow.io | admitted |
| outlook.com | admitted |
| microsoft365.io | admitted |
| gstatic.com | admitted |
| datadoghq.com | admitted |
| typekit.net | admitted |
| sharepoint.com | admitted |

### Rejected Missed by AOD

**3 assets should have been rejected but weren't**

- `openforce.net`
- `netbox.net`
- `salesforce-crm.com`

### Admission False Positives (Cataloged)

**5 assets AOD cataloged but Farm expected rejection**

These assets should have been rejected (not admitted) based on Farm's admission policy.

| Asset Key | Discovery Sources | Rejection Reason | Farm Reason Codes |
|-----------|-------------------|------------------|-------------------|
| `datadog.com` | 0 (none) | None | N/A |
| `openforce.net` | 1 (proxy) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `netbox.net` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `salesforce-crm.com` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `adobe.com` | 0 (none) | None | N/A |

### Admission False Positives (Rejected)

**14 assets AOD rejected but Farm expected admission**

| Asset Key | Discovery Sources | Farm Reason Codes |
|-----------|-------------------|-------------------|
| `pivotaltracker.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `tiktok.com` | 2 (dns, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `googleusercontent.com` | 1 (endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coresuite.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `basecamp.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workers.dev` | 2 (browser, network_scan) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `cloudfront.net` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `coreflow.io` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `outlook.com` | 2 (endpoint, proxy) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `microsoft365.io` | 1 (browser) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `gstatic.com` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datadoghq.com` | 3 (browser, endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `typekit.net` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `sharepoint.com` | 2 (browser, dns) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |

---

## Root Cause Analysis Summary

| RCA Hint | Count |
|----------|-------|
| KEY_NORMALIZATION_MISMATCH | 16 |
| FP_FROM_CLEAN | 3 |
| UNGOVERNED_ACTIVE | 2 |
| FP_FROM_UNKNOWN | 1 |
| FP_FROM_NOT-ADMITTED | 1 |

---

## Recommendations

- **Key Normalization:** AOD has evidence for some assets but is not using the expected canonical keys. Review key normalization logic.
- **Finance Governance:** 2 assets have `HAS_ONGOING_FINANCE` but AOD classified as shadow. Consider treating ongoing finance as governance.
- **Shadow Detection:** 4 expected shadows not found. Check shadow classification rules.
- **Zombie Detection:** 14 expected zombies not found. Check zombie classification rules.

---

*Generated by AOS Farm Assessment Engine*