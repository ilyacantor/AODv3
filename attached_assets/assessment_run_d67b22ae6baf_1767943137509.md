# Reconciliation Assessment Report

**AOD Run:** `run_d67b22ae6baf`
**Reconciliation ID:** `b44f2682-30b8-4a0c-b26f-82e964de7752`
**Snapshot ID:** `65987a5a-2555-48ee-a283-96c7ed4f07c5`
**Tenant:** `DataDynamics-V4S5`
**Generated:** 2026-01-09T07:14:21.569500Z

---

## Executive Summary

**Overall Status:** FAIL
**Verdict:** NEEDS WORK - classification missed 39/109
**Combined Accuracy:** 78.2%

### Summary Table

| Category | Farm Expected | AOD Found | Matched | Missed | FP |
|----------|---------------|-----------|---------|--------|-----|
| Shadows | 72 | 68 | 67 | 5 | 7 |
| Zombies | 37 | 3 | 3 | 34 | 0 |

### Lifecycle Funnel

- **Gross Observations:** 3347
- **Unique Assets:** 1298
- **Rejected (not admitted):** 707
- **Admitted:** 591
- **Cataloged (final):** 591

---

## Classification Analysis

### Matched Shadows (Correctly Identified)

**67 assets correctly identified as Shadow IT**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| maxcloud.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| rapidbase.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| hubsoft.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| proflow.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| primefy.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| maxsuite.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| datatech.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| airtable.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| calendly.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flexspace.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| hubpoint.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| primedesk.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| rapidsync.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| canva.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| monday.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| cloudworks.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| clickup.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| ultrabase.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| smartsoft.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| cloudflareinsights.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| cloudfront.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| datapoint.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flowify.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| primeify.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| openforce.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flexhub.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| typeform.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flowbase.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flowify.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| hubbox.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flexspace.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| worksync.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flowworks.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| easyspace.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| snowflakecomputing.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flowpoint.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| opencloud.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| dataspace.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| miro.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| rapidbase.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| zapier.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| ultrafy.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| datasuite.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| dataify.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| workbox.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flowspace.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| openbox.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| easybox.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| maxflow.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flowcloud.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| easyspace.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| dropbox.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| surveymonkey.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| evernote.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| synctech.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| opensync.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| flowflow.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| opencloud.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| proflow.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| openapp.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| smartworks.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| netbase.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| datahub.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| easyfy.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| loom.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| flexfy.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |
| okta.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB | UNGOVERNED_ACTIVE |

### Missed Shadows (False Negatives)

**5 assets missed by AOD - should have been Shadow IT**

#### `primetech.cloud`

**Headline:** AOD missed primetech.cloud as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `amazon.com`

**Headline:** AOD missed amazon.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for amazon.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, HAS_CLOUD, RECENT_ACTIVITY`

#### `tiktok.com`

**Headline:** AOD missed tiktok.com as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

#### `typekit.net`

**Headline:** AOD missed typekit.net as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

#### `workers.dev`

**Headline:** AOD missed workers.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for workers.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

### False Positive Shadows

**7 assets incorrectly classified as Shadow IT by AOD**

#### Farm Classification: `clean` (2 assets)

**`salesforceliveagent.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY, GOVERNED_VIA_VENDOR`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, SHADOW_CLASSIFICATION, NOT_ANCHORED, NO_IDP`
- **In Farm only:** `GOVERNED_VIA_VENDOR, HAS_CMDB, HAS_ONGOING_FINANCE, HAS_SECURITY_ATTESTATION, HAS_IDP, HAS_FINANCE, GOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, NO_ONGOING_FINANCE, NO_CMDB, NO_FINANCE, SHADOW_CLASSIFICATION, NOT_ANCHORED, NO_IDP`

**`microsoft.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, HAS_DISCOVERY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, HAS_CMDB, NOT_ANCHORED, HAS_ONGOING_FINANCE, NO_IDP, HAS_FINANCE`
- **In Farm only:** `HAS_SECURITY_ATTESTATION, GOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, NOT_ANCHORED`

#### Farm Classification: `not-admitted` (4 assets)

**`probox.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP, HAS_ONGOING_FINANCE, NO_IDP, HAS_FINANCE`
- **In Farm only:** `HAS_SECURITY_ATTESTATION, STALE_ACTIVITY, UNGOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP`

**`primetech.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP, HAS_ONGOING_FINANCE, NO_IDP, HAS_FINANCE`
- **In Farm only:** `HAS_SECURITY_ATTESTATION, UNGOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP`

**`netbox.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP, HAS_ONGOING_FINANCE, NO_IDP, HAS_FINANCE`
- **In Farm only:** `NO_SECURITY_ATTESTATION, UNGOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP`

**`easyio.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_CMDB, HAS_DISCOVERY, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP, HAS_ONGOING_FINANCE, NO_IDP, HAS_FINANCE`
- **In Farm only:** `HAS_SECURITY_ATTESTATION, UNGOVERNED`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, FINANCIALLY_ANCHORED, ANCHORED, SHADOW_CLASSIFICATION, FINANCIAL_ANCHOR_GOVERNANCE_GAP`

#### Farm Classification: `unknown` (1 assets)

**`adobe.com`**

- **Farm Reason Codes:** ``
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, SHADOW_CLASSIFICATION, NOT_ANCHORED, NO_IDP`
- **In AOD only:** `DISCOVERY_SOURCE_COUNT_GE_2, RECENT_ACTIVITY, NO_ONGOING_FINANCE, NO_CMDB, HAS_DISCOVERY, NO_FINANCE, SHADOW_CLASSIFICATION, NOT_ANCHORED, NO_IDP`

### Matched Zombies (Correctly Identified)

**3 assets correctly identified as Zombie**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| zoom-legacy.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | STALE_ACTIVITY, DISCOVERY_SOURCE_COUNT_GE_2, HAS_DISCOVERY, FINANCIALLY_ANCHORED | STALE_NO_RECENT_USE |
| yammer.com | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | STALE_ACTIVITY, DISCOVERY_SOURCE_COUNT_GE_2, HAS_DISCOVERY, FINANCIALLY_ANCHORED | STALE_NO_RECENT_USE |
| hipchat.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | STALE_ACTIVITY, DISCOVERY_SOURCE_COUNT_GE_2, HAS_DISCOVERY, FINANCIALLY_ANCHORED | STALE_NO_RECENT_USE |

### Missed Zombies (False Negatives)

**34 assets missed by AOD - should have been Zombie**

#### `linkio.org`

**Headline:** AOD missed linkio.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linkio.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `probase.com`

**Headline:** AOD missed probase.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `rapiddesk.com`

**Headline:** AOD missed rapiddesk.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for rapiddesk.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flowly.co`

**Headline:** AOD missed flowly.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flowly.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easyworks.co`

**Headline:** AOD missed easyworks.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easyworks.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `linkly.tech`

**Headline:** AOD missed linkly.tech as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `corespace.ai`

**Headline:** AOD missed corespace.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for corespace.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `smarthub.co`

**Headline:** AOD missed smarthub.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for smarthub.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flexbase.org`

**Headline:** AOD missed flexbase.org as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flexflow.org`

**Headline:** AOD missed flexflow.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flexflow.org but did not normalize to domain key
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

#### `probase.ai`

**Headline:** AOD missed probase.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fastspace.co`

**Headline:** AOD missed fastspace.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fastspace.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `workcloud.cloud`

**Headline:** AOD missed workcloud.cloud as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `protech.com`

**Headline:** AOD missed protech.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for protech.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `ultraflow.dev`

**Headline:** AOD missed ultraflow.dev as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `openio.ai`

**Headline:** AOD missed openio.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for openio.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `cloudcloud.ai`

**Headline:** AOD missed cloudcloud.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for cloudcloud.ai but did not normalize to domain key
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

#### `linktech.org`

**Headline:** AOD missed linktech.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linktech.org but did not normalize to domain key
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

#### `probase.org`

**Headline:** AOD missed probase.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for probase.org but did not normalize to domain key
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

#### `fasthub.dev`

**Headline:** AOD missed fasthub.dev as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `cloudcloud.com`

**Headline:** AOD missed cloudcloud.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for cloudcloud.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flowly.app`

**Headline:** AOD missed flowly.app as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flowly.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `opensoft.org`

**Headline:** AOD missed opensoft.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for opensoft.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `cloudapp.dev`

**Headline:** AOD missed cloudapp.dev as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fasthub.co`

**Headline:** AOD missed fasthub.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fasthub.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `maxfy.co`

**Headline:** AOD missed maxfy.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for maxfy.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flexflow.com`

**Headline:** AOD missed flexflow.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flexflow.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `syncdesk.tech`

**Headline:** AOD missed syncdesk.tech as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for syncdesk.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `ultralabs.co`

**Headline:** AOD missed ultralabs.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for ultralabs.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

---

## Admission Analysis

### Admission Metrics

- **Total Assets:** 1298
- **Matched:** 1036
- **Missed:** 262
- **False Positives:** 264
- **Accuracy:** 79.8%

### Cataloged Missed by AOD

**252 assets should have been cataloged but weren't**

| Asset | Farm Classification |
|-------|---------------------|
| flexworks.io | admitted |
| maxcloud.app | admitted |
| syncio.tech | admitted |
| easypoint.app | admitted |
| corecloud.org | admitted |
| rapiddesk.com | admitted |
| pivotaltracker.com | admitted |
| smartsync.app | admitted |
| opensoft.dev | admitted |
| smartpoint.com | admitted |
| coreworks.tech | admitted |
| coreflow.io | admitted |
| flexworks.cloud | admitted |
| flexworks.dev | admitted |
| salesforce.io | admitted |
| openio.tech | admitted |
| teamsync.org | admitted |
| easysuite.app | admitted |
| cloudsoft.com | admitted |
| googleusercontent.com | admitted |
| ... | (232 more) |

### Rejected Missed by AOD

**10 assets should have been rejected but weren't**

- `easyio.net`
- `openbox.io`
- `primetech.ai`
- `smartworks.com`
- `probox.net`
- `salesforce-crm.com`
- `maxcloud.org`
- `flexfy.com`
- `netbox.net`
- `netbase.io`

### Admission False Positives (Cataloged)

**12 assets AOD cataloged but Farm expected rejection**

These assets should have been rejected (not admitted) based on Farm's admission policy.

| Asset Key | Discovery Sources | Rejection Reason | Farm Reason Codes |
|-----------|-------------------|------------------|-------------------|
| `easyio.net` | 1 (saas_audit_log) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `openbox.io` | 0 (none) | No discovery sources | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `primetech.ai` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `smartworks.com` | 1 (saas_audit_log) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `adobe.com` | 0 (none) | None | N/A |
| `probox.net` | 0 (none) | No discovery sources | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `salesforce-crm.com` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `maxcloud.org` | 1 (proxy) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `datadog.com` | 0 (none) | None | N/A |
| `flexfy.com` | 0 (none) | No discovery sources | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `netbox.net` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `netbase.io` | 1 (dns) | Single source | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |

### Admission False Positives (Rejected)

**252 assets AOD rejected but Farm expected admission**

| Asset Key | Discovery Sources | Farm Reason Codes |
|-----------|-------------------|-------------------|
| `flexworks.io` | 2 (browser, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxcloud.app` | 2 (browser, dns) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `syncio.tech` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easypoint.app` | 1 (endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corecloud.org` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapiddesk.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `pivotaltracker.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartsync.app` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `opensoft.dev` | 2 (dns, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartpoint.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coreworks.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coreflow.io` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexworks.cloud` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexworks.dev` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `salesforce.io` | 1 (dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openio.tech` | 2 (browser, endpoint) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamsync.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easysuite.app` | 2 (browser, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudsoft.com` | 1 (cloud_api) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `googleusercontent.com` | 1 (endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datadynamics-v4s5.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `teamio.co` | 2 (browser, cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workio.tech` | 1 (cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultracloud.org` | 1 (endpoint) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowio.co` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primelabs.com` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubsync.tech` | 2 (dns, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `synchub.com` | 2 (browser, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `probase.tech` | 2 (browser, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workspace.com` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primesuite.com` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastdesk.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxdesk.ai` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexworks.app` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netly.co` | 2 (browser, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamify.org` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidtech.tech` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `fastpoint.cloud` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudbox.cloud` | 2 (browser, network_scan) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `nettech.dev` | 2 (endpoint, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easybase.dev` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openhub.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easyspace.com` | 2 (browser, cloud_api) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `datafy.dev` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `outlook.com` | 2 (endpoint, proxy) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `maxlabs.ai` | 1 (cloud_api) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkcloud.dev` | 1 (endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidsoft.app` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkforce.co` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamlabs.app` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easycloud.cloud` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudtech.com` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coresync.app` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fasthub.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartapp.cloud` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartflow.tech` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flextech.io` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamio.com` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowly.net` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primely.tech` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `proify.ai` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidify.net` | 2 (browser, cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncsuite.co` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netpoint.org` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netcloud.com` | 2 (browser, network_scan) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flextech.dev` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easybase.net` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `profy.tech` | 2 (browser, cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastapp.com` | 2 (dns, proxy) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workcloud.org` | 2 (network_scan, proxy) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primehub.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corecloud.dev` | 2 (browser, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastlabs.dev` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workbase.app` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netflow.org` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastly.cloud` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openlabs.cloud` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workforce.co` | 1 (saas_audit_log) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `nettech.tech` | 2 (cloud_api, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastio.io` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datasync.net` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastpoint.tech` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coresuite.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primespace.com` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidsuite.com` | 2 (cloud_api, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `opencloud.tech` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `proio.net` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easybase.tech` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidbase.cloud` | 2 (endpoint, network_scan) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `corelabs.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `proly.org` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidify.com` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netflow.ai` | 2 (browser, cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamsuite.net` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easydesk.tech` | 2 (endpoint, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easyflow.co` | 1 (cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamworks.io` | 1 (proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `probase.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openbox.cloud` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `fastbase.org` | 2 (browser, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datadoghq.com` | 3 (browser, endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexio.app` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubbase.cloud` | 1 (proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultraly.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamify.io` | 2 (endpoint, proxy) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easysuite.co` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `protech.ai` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxapp.io` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `coresync.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartworks.ai` | 2 (network_scan, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `syncforce.com` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primeforce.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corespace.tech` | 2 (browser, endpoint) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datadesk.io` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubtech.dev` | 1 (dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teampoint.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corebox.dev` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexflow.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `probase.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `proflow.tech` | 2 (cloud_api, dns) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `datasync.org` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudify.cloud` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastapp.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primehub.ai` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudly.com` | 1 (cloud_api) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `basecamp.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidify.cloud` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastspace.ai` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncflow.app` | 2 (browser, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncspace.app` | 2 (endpoint, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corepoint.dev` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudhub.app` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncforce.net` | 2 (endpoint, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxtech.dev` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `prosync.cloud` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxfy.net` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowio.cloud` | 1 (dns) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `amazon.com` | 2 (network_scan, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `maxpoint.cloud` | 2 (browser, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowify.cloud` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `workcloud.cloud` | 0 (none) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linktech.cloud` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `atlassian.com` | 1 (cloud_api) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `maxsync.ai` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkcloud.cloud` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamio.dev` | 1 (cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudcloud.app` | 2 (browser, cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxbase.dev` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowhub.ai` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `tiktok.com` | 2 (dns, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `smartflow.net` | 2 (endpoint, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubly.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `microsoft365.io` | 1 (browser) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `netfy.com` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartflow.org` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxpoint.com` | 1 (dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultrasoft.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workbase.io` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastsuite.tech` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easypoint.cloud` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudcloud.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netify.com` | 3 (browser, dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workforce.ai` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smartapp.tech` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkbase.tech` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudly.tech` | 2 (endpoint, proxy) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudapp.dev` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexworks.org` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `corely.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkworks.org` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netsync.app` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openio.dev` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamsoft.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datasync.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easysync.org` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openly.co` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `netpoint.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primely.ai` | 2 (browser, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `prohub.org` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workly.dev` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workers.dev` | 2 (browser, network_scan) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `cloudsuite.ai` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubdesk.ai` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `smarthub.dev` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkio.org` | 0 (none) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexsuite.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowfy.tech` | 2 (dns, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easyworks.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openify.io` | 2 (dns, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncdesk.com` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkly.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudcloud.dev` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openspace.tech` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamflow.app` | 2 (dns, endpoint) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexbase.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `worktech.app` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `sharepoint.com` | 2 (browser, dns) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `flexfy.cloud` | 2 (browser, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `flexflow.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primehub.dev` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubhub.tech` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primetech.cloud` | 2 (browser, saas_audit_log) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `primesuite.cloud` | 1 (proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubbase.org` | 2 (browser, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowbox.app` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultralabs.net` | 2 (dns, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `cloudio.net` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkapp.ai` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexspace.com` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `prosuite.co` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workify.net` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultraflow.dev` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workapp.cloud` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workhub.tech` | 2 (dns, network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `datadesk.app` | 2 (cloud_api, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `proly.tech` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `proio.org` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flexcloud.io` | 1 (endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `primelabs.dev` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubbase.net` | 1 (proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `syncio.com` | 2 (cloud_api, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easycloud.io` | 1 (cloud_api) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easycloud.tech` | 2 (browser, dns) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubtech.net` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primesuite.tech` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultraly.app` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidsuite.cloud` | 2 (browser, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `typekit.net` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `coreforce.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netlabs.tech` | 2 (cloud_api, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `worklabs.org` | 2 (cloud_api, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidlabs.cloud` | 2 (endpoint, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fasthub.dev` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `gstatic.com` | 1 (saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `prohub.com` | 2 (network_scan, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `openify.com` | 2 (browser, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowly.app` | 0 (none) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `flowforce.org` | 2 (proxy, saas_audit_log) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `teamsync.net` | 1 (browser) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `maxspace.tech` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `hubhub.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `primeflow.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastio.app` | 1 (network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `netbase.cloud` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, UNGOVERNED... |
| `smartapp.app` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `prospace.net` | 0 (none) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fastio.ai` | 2 (dns, endpoint) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linktech.com` | 2 (browser, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `workify.app` | 2 (network_scan, saas_audit_log) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultrasync.cloud` | 2 (dns, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `rapidsuite.io` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `ultralabs.co` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |

---

## Root Cause Analysis Summary

| RCA Hint | Count |
|----------|-------|
| KEY_NORMALIZATION_MISMATCH | 30 |
| STALE_NO_RECENT_USE | 6 |
| FP_FROM_NOT-ADMITTED | 4 |
| UNGOVERNED_ACTIVE | 3 |
| FP_FROM_CLEAN | 2 |
| FP_FROM_UNKNOWN | 1 |

---

## Recommendations

- **Key Normalization:** AOD has evidence for some assets but is not using the expected canonical keys. Review key normalization logic.
- **Finance Governance:** 2 assets have `HAS_ONGOING_FINANCE` but AOD classified as shadow. Consider treating ongoing finance as governance.
- **Shadow Detection:** 5 expected shadows not found. Check shadow classification rules.
- **Zombie Detection:** 34 expected zombies not found. Check zombie classification rules.

---

*Generated by AOS Farm Assessment Engine*