# Reconciliation Assessment Report

**AOD Run:** `run_0dca3a4bf8b3`
**Reconciliation ID:** `539326eb-855b-4d43-9bc9-e3d68a67387b`
**Snapshot ID:** `af6e9348-a5c7-457e-9291-a6b1d3ca8f5f`
**Tenant:** `HelixLogic-9GC6`
**Generated:** 2026-01-05T11:01:59.872648Z

---

## Executive Summary

**Overall Status:** FAIL
**Verdict:** NEEDS WORK - classification missed 27/113
**Combined Accuracy:** 97.2%

### Summary Table

| Category | Farm Expected | AOD Found | Matched | Missed | FP |
|----------|---------------|-----------|---------|--------|-----|
| Shadows | 57 | 56 | 56 | 1 | 0 |
| Zombies | 56 | 30 | 30 | 26 | 0 |

### Lifecycle Funnel

- **Gross Observations:** 23561
- **Unique Assets:** 1163
- **Rejected (not admitted):** 550
- **Admitted:** 613
- **Cataloged (final):** 613

---

## Classification Analysis

### Matched Shadows (Correctly Identified)

**56 assets correctly identified as Shadow IT**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| opensuite.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| airtable.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| teamly.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| linkly.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| teamlabs.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| easybase.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| smartly.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| rapidflow.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| teamlabs.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| proflow.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| fastcloud.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| fastforce.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| webex.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| openhub.app | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| flowsync.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| smartio.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| opensync.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| loom.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| hubly.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| corebox.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| surveymonkey.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| smartio.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| workfy.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| datasoft.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| smartpoint.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| opendesk.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| smartly.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| propoint.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| evernote.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| ultrabase.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| syncflow.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| workcloud.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| flexapp.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| openworks.tech | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| ultrabox.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| teambox.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| canva.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| flowpoint.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| primecloud.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| teambase.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| flexhub.ai | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| ultrahub.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| cloudbase.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| flowsuite.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| calendly.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| typeform.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| linkbase.com | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| easyhub.co | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| easyapp.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| dataio.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| openworks.cloud | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| ultrabase.io | HAS_DISCOVERY, NO_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| flowsoft.net | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| flexify.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |
| rapidcloud.org | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | NO_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | UNGOVERNED_ACTIVE |
| dataio.dev | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, FINANCIAL_ANCHOR_GOVERNANCE_GAP, NO_IDP | UNGOVERNED_ACTIVE |

### Missed Shadows (False Negatives)

**1 assets missed by AOD - should have been Shadow IT**

#### `tiktok.com`

**Headline:** AOD missed tiktok.com as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED, RECENT_ACTIVITY`

### Matched Zombies (Correctly Identified)

**30 assets correctly identified as Zombie**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| corely.app | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| openspace.tech | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| smartfy.io | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| opentech.app | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| fastbox.co | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| dataforce.net | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| fastify.io | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| smartbase.org | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| rapidsoft.net | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| rapidsync.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| cloudspace.org | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| rapidfy.com | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| fastify.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| maxtech.app | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| easybox.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| smartbox.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| workbox.net | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| rapidpoint.org | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| rapidsoft.ai | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| smartapp.app | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| zoom-legacy.com | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| openforce.tech | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| syncbase.ai | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| smartbase.co | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION | HAS_FINANCE, NO_CMDB, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| primespace.io | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |
| syncsync.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| hubapp.co | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| netspace.app | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| fastify.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, ANCHORED, HAS_ONGOING_FINANCE | STALE_NO_RECENT_USE |
| opencloud.com | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION | HAS_CMDB, HAS_FINANCE, NO_IDP, ANCHORED | STALE_NO_RECENT_USE |

### Missed Zombies (False Negatives)

**26 assets missed by AOD - should have been Zombie**

#### `fastsuite.ai`

**Headline:** AOD missed fastsuite.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fastsuite.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `hipchat.com`

**Headline:** AOD missed hipchat.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for hipchat.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `syncify.app`

**Headline:** AOD missed syncify.app as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for syncify.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `netlabs.dev`

**Headline:** AOD missed netlabs.dev as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for netlabs.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `worksync.com`

**Headline:** AOD missed worksync.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for worksync.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `netpoint.app`

**Headline:** AOD missed netpoint.app as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for netpoint.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `primepoint.dev`

**Headline:** AOD missed primepoint.dev as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for primepoint.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flowbox.co`

**Headline:** AOD missed flowbox.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flowbox.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `maxsuite.io`

**Headline:** AOD missed maxsuite.io as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for maxsuite.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `linkforce.tech`

**Headline:** AOD missed linkforce.tech as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linkforce.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `linkhub.ai`

**Headline:** AOD missed linkhub.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linkhub.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `linksuite.io`

**Headline:** AOD missed linksuite.io as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linksuite.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `databox.net`

**Headline:** AOD missed databox.net as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for databox.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `flowbox.ai`

**Headline:** AOD missed flowbox.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for flowbox.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fasttech.co`

**Headline:** AOD missed fasttech.co as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fasttech.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easylabs.app`

**Headline:** AOD missed easylabs.app as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easylabs.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easycloud.cloud`

**Headline:** AOD missed easycloud.cloud as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easycloud.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easyify.app`

**Headline:** AOD missed easyify.app as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easyify.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `coreworks.ai`

**Headline:** AOD missed coreworks.ai as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for coreworks.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `linksuite.org`

**Headline:** AOD missed linksuite.org as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for linksuite.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `fastio.tech`

**Headline:** AOD missed fastio.tech as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for fastio.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `hubify.com`

**Headline:** AOD missed hubify.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for hubify.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `netsoft.tech`

**Headline:** AOD missed netsoft.tech as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for netsoft.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easyspace.dev`

**Headline:** AOD missed easyspace.dev as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easyspace.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `easycloud.tech`

**Headline:** AOD missed easycloud.tech as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for easycloud.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

#### `yammer.com`

**Headline:** AOD missed yammer.com as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION
- **AOD Detail:** AOD has evidence for yammer.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`

---

## Admission Analysis

### Admission Metrics

- **Total Assets:** 1163
- **Matched:** 1154
- **Missed:** 9
- **False Positives:** 10
- **Accuracy:** 99.2%

### Cataloged Missed by AOD

**9 assets should have been cataloged but weren't**

| Asset | Farm Classification |
|-------|---------------------|
| linkspace.ai | admitted |
| datadoghq.com | admitted |
| linkspace.cloud | admitted |
| easysoft.org | admitted |
| fasthub.dev | admitted |
| helixlogic-9gc6.com | admitted |
| primeio.cloud | admitted |
| tiktok.com | admitted |
| databox.net | admitted |

### Admission False Positives (Cataloged)

**1 assets AOD cataloged but Farm expected rejection**

These assets should have been rejected (not admitted) based on Farm's admission policy.

| Asset Key | Discovery Sources | Rejection Reason | Farm Reason Codes |
|-----------|-------------------|------------------|-------------------|
| `datadog.com` | 0 (none) | None | N/A |

### Admission False Positives (Rejected)

**9 assets AOD rejected but Farm expected admission**

| Asset Key | Discovery Sources | Farm Reason Codes |
|-----------|-------------------|-------------------|
| `linkspace.ai` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `datadoghq.com` | 3 (browser, cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, NO_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `linkspace.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `easysoft.org` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `fasthub.dev` | 0 (none) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `helixlogic-9gc6.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, NO_SECURITY_ATTESTATION, GOVERNED... |
| `primeio.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |
| `tiktok.com` | 2 (dns, proxy) | HAS_DISCOVERY, NO_IDP, NO_CMDB, NO_SECURITY_ATTESTATION, UNGOVERNED... |
| `databox.net` | 0 (none) | HAS_DISCOVERY, NO_IDP, HAS_CMDB, HAS_SECURITY_ATTESTATION, GOVERNED... |

---

## Root Cause Analysis Summary

| RCA Hint | Count |
|----------|-------|
| KEY_NORMALIZATION_MISMATCH | 26 |
| UNGOVERNED_ACTIVE | 1 |

---

## Recommendations

- **Key Normalization:** AOD has evidence for some assets but is not using the expected canonical keys. Review key normalization logic.
- **Shadow Detection:** 1 expected shadows not found. Check shadow classification rules.
- **Zombie Detection:** 26 expected zombies not found. Check zombie classification rules.

---

*Generated by AOS Farm Assessment Engine*