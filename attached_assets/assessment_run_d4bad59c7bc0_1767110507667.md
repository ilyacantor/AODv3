# Reconciliation Assessment Report

**AOD Run:** `run_d4bad59c7bc0`
**Reconciliation ID:** `1971d8be-aa43-47ba-b93e-9039807901b3`
**Snapshot ID:** `387428ff-f30e-4f8e-8838-772aa79939d4`
**Tenant:** `ApexLogic-H8KP`
**Generated:** 2025-12-30T15:56:33.620987Z

---

## Executive Summary

**Overall Status:** FAIL
**Verdict:** NEEDS WORK - classification missed 95/242
**Combined Accuracy:** 89.2%

### Summary Table

| Category | Farm Expected | AOD Found | Matched | Missed | FP |
|----------|---------------|-----------|---------|--------|-----|
| Shadows | 196 | 56 | 103 | 93 | 0 |
| Zombies | 46 | 99 | 44 | 2 | 53 |

### Lifecycle Funnel

- **Gross Observations:** 24356
- **Unique Assets:** 1155
- **Rejected (not admitted):** 554
- **Admitted:** 601
- **Cataloged (final):** 601

---

## Classification Analysis

### Matched Shadows (Correctly Identified)

**103 assets correctly identified as Shadow IT**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| flowbox.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| openlabs.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| coresoft.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| primebox.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudify.io | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| workapp.io | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| airtable.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| easyworks.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| syncapp.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| smartcloud.ai | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| easyify.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| maxlabs.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| cloudify.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| teamsoft.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| cloudify.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| fastbox.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| rapidcloud.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| maxworks.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| webex.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| easyio.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| prolabs.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| hubsoft.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudsync.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| ultracloud.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| maxworks.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| primespace.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| fastbox.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxforce.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| hubspot.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| syncsoft.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudsync.ai | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| datadesk.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudworks.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| canva.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| calendly.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudify.ai | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| openlabs.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| openpoint.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| syncly.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudfy.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| opensoft.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| dataspace.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| linktech.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| teamspace.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudforce.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxworks.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| flowcloud.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| primespace.co | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| loom.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY | UNGOVERNED_ACTIVE |
| docusign.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| worktech.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudapp.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| box.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| easybase.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxsuite.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| cloudworks.org | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| syncforce.co | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxforce.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| ultraio.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxflow.io | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| cloudfy.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| fasthub.co | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| openapp.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudcloud.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| smartdesk.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| grammarly.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| evernote.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| openpoint.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| nethub.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| linkpoint.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| flowspace.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| cloudcloud.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| proworks.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| easyify.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| datacloud.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| hubsync.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| primebox.org | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| smartbase.co | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxify.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| maxsync.ai | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| fastworks.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| dataapp.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| teambase.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| primecloud.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| fastlabs.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| hubtech.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| rapidsync.dev | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| maxapp.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| coreflow.app | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| snowflakecomputing.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY | - |
| opentech.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| flexio.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| zapier.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| openapp.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| openbase.io | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| proify.tech | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| opencloud.com | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| maxdesk.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| prosync.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| workflow.cloud | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| fastapp.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | UNGOVERNED_ACTIVE |
| procloud.net | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |
| netcloud.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB | SHADOW_CLASSIFICATION, DISCOVERY_SOURCE_COUNT_LT_2, HAS_DISCOVERY, HAS_FINANCE | - |

### Missed Shadows (False Negatives)

**93 assets missed by AOD - should have been Shadow IT**

#### `teamsoft.net`

**Headline:** AOD missed teamsoft.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for teamsoft.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `netflow.dev`

**Headline:** AOD missed netflow.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for netflow.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `teamlabs.net`

**Headline:** AOD missed teamlabs.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for teamlabs.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `primepoint.dev`

**Headline:** AOD missed primepoint.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for primepoint.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linksoft.tech`

**Headline:** AOD missed linksoft.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for linksoft.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datasync.io`

**Headline:** AOD missed datasync.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datasync.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubforce.tech`

**Headline:** AOD missed hubforce.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for hubforce.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidio.app`

**Headline:** AOD missed rapidio.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for rapidio.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flexsoft.io`

**Headline:** AOD missed flexsoft.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flexsoft.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubbase.co`

**Headline:** AOD missed hubbase.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for hubbase.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `fastworks.dev`

**Headline:** AOD missed fastworks.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for fastworks.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubforce.app`

**Headline:** AOD missed hubforce.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for hubforce.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `nettech.dev`

**Headline:** AOD missed nettech.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for nettech.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultratech.org`

**Headline:** AOD missed ultratech.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for ultratech.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datasync.com`

**Headline:** AOD missed datasync.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datasync.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncdesk.org`

**Headline:** AOD missed syncdesk.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncdesk.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `teampoint.tech`

**Headline:** AOD missed teampoint.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for teampoint.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncio.org`

**Headline:** AOD missed syncio.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for syncio.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workfy.co`

**Headline:** AOD missed workfy.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for workfy.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linkify.app`

**Headline:** AOD missed linkify.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for linkify.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datadoghq.com`

**Headline:** AOD missed datadoghq.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for datadoghq.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubsuite.app`

**Headline:** AOD missed hubsuite.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubsuite.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowfy.io`

**Headline:** AOD missed flowfy.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flowfy.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncdesk.io`

**Headline:** AOD missed syncdesk.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncdesk.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linkdesk.dev`

**Headline:** AOD missed linkdesk.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for linkdesk.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, RECENT_ACTIVITY`

#### `fastlabs.io`

**Headline:** AOD missed fastlabs.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for fastlabs.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `fastsoft.com`

**Headline:** AOD missed fastsoft.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for fastsoft.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncfy.dev`

**Headline:** AOD missed syncfy.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncfy.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncify.co`

**Headline:** AOD missed syncify.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncify.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowlabs.org`

**Headline:** AOD missed flowlabs.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flowlabs.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `okta.com`

**Headline:** AOD missed okta.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for okta.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `figma.com`

**Headline:** AOD missed figma.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for figma.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `notion.so`

**Headline:** AOD missed notion.so as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for notion.so but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `zendesk.com`

**Headline:** AOD missed zendesk.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for zendesk.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncdesk.com`

**Headline:** AOD missed syncdesk.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncdesk.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `google.com`

**Headline:** AOD missed google.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for google.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidpoint.co`

**Headline:** AOD missed rapidpoint.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for rapidpoint.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidify.dev`

**Headline:** AOD missed rapidify.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for rapidify.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `dataworks.org`

**Headline:** AOD missed dataworks.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for dataworks.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `coreforce.ai`

**Headline:** AOD missed coreforce.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for coreforce.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workworks.app`

**Headline:** AOD missed workworks.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for workworks.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workday.com`

**Headline:** AOD missed workday.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for workday.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `dataly.ai`

**Headline:** AOD missed dataly.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for dataly.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `profy.app`

**Headline:** AOD missed profy.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for profy.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `netflow.io`

**Headline:** AOD missed netflow.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for netflow.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidio.tech`

**Headline:** AOD missed rapidio.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for rapidio.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultratech.app`

**Headline:** AOD missed ultratech.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for ultratech.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `netpoint.dev`

**Headline:** AOD missed netpoint.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for netpoint.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartio.tech`

**Headline:** AOD missed smartio.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for smartio.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, RECENT_ACTIVITY`

#### `hubsuite.co`

**Headline:** AOD missed hubsuite.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubsuite.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `servicenow.com`

**Headline:** AOD missed servicenow.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for servicenow.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `coreio.tech`

**Headline:** AOD missed coreio.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for coreio.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `teamworks.dev`

**Headline:** AOD missed teamworks.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for teamworks.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datasuite.app`

**Headline:** AOD missed datasuite.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datasuite.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flexflow.tech`

**Headline:** AOD missed flexflow.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flexflow.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubsync.io`

**Headline:** AOD missed hubsync.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubsync.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultradesk.tech`

**Headline:** AOD missed ultradesk.tech as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for ultradesk.tech but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `coreforce.dev`

**Headline:** AOD missed coreforce.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for coreforce.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidtech.org`

**Headline:** AOD missed rapidtech.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for rapidtech.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncpoint.io`

**Headline:** AOD missed syncpoint.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for syncpoint.io but did not normalize to domain key
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

#### `ultrasoft.io`

**Headline:** AOD missed ultrasoft.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for ultrasoft.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultradesk.com`

**Headline:** AOD missed ultradesk.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for ultradesk.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datasync.dev`

**Headline:** AOD missed datasync.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datasync.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `teamworks.io`

**Headline:** AOD missed teamworks.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for teamworks.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartfy.co`

**Headline:** AOD missed smartfy.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for smartfy.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncify.net`

**Headline:** AOD missed syncify.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for syncify.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `ultrasuite.app`

**Headline:** AOD missed ultrasuite.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for ultrasuite.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartfy.ai`

**Headline:** AOD missed smartfy.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for smartfy.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `smartlabs.dev`

**Headline:** AOD missed smartlabs.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for smartlabs.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `tiktok.com`

**Headline:** AOD missed tiktok.com as shadow IT - active but missing from governance systems

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `UNGOVERNED_ACTIVE`
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, RECENT_ACTIVITY`

#### `hubflow.org`

**Headline:** AOD missed hubflow.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubflow.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `proflow.dev`

**Headline:** AOD missed proflow.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for proflow.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncio.app`

**Headline:** AOD missed syncio.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for syncio.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `apexlogic-h8kp.com`

**Headline:** AOD missed apexlogic-h8kp.com as shadow IT

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `None`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, RECENT_ACTIVITY`

#### `worklabs.net`

**Headline:** AOD missed worklabs.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for worklabs.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `nettech.co`

**Headline:** AOD missed nettech.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for nettech.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `worksync.org`

**Headline:** AOD missed worksync.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for worksync.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `fastsoft.ai`

**Headline:** AOD missed fastsoft.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for fastsoft.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubworks.org`

**Headline:** AOD missed hubworks.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubworks.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `dataly.io`

**Headline:** AOD missed dataly.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for dataly.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `primely.ai`

**Headline:** AOD missed primely.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for primely.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `flowlabs.dev`

**Headline:** AOD missed flowlabs.dev as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for flowlabs.dev but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workapp.ai`

**Headline:** AOD missed workapp.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for workapp.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `rapidforce.ai`

**Headline:** AOD missed rapidforce.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for rapidforce.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datatech.co`

**Headline:** AOD missed datatech.co as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datatech.co but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `teampoint.org`

**Headline:** AOD missed teampoint.org as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for teampoint.org but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `dropbox.com`

**Headline:** AOD missed dropbox.com as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for dropbox.com but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `syncpoint.app`

**Headline:** AOD missed syncpoint.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for syncpoint.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `datatech.io`

**Headline:** AOD missed datatech.io as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for datatech.io but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `hubworks.app`

**Headline:** AOD missed hubworks.app as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for hubworks.app but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `linksuite.net`

**Headline:** AOD missed linksuite.net as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for linksuite.net but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, NO_SECURITY_ATTESTATION, MISSING_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

#### `workfy.ai`

**Headline:** AOD missed workfy.ai as shadow IT - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected SHADOW because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB
- **AOD Detail:** AOD has evidence for workfy.ai but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`

### Matched Zombies (Correctly Identified)

**44 assets correctly identified as Zombie**

| Asset | Farm Reason Codes | AOD Reason Codes | RCA Hint |
|-------|-------------------|------------------|----------|
| ultraly.ai | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| easyfy.org | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| opensuite.net | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| syncsync.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| datahub.app | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| worksuite.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| linkforce.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| linkbox.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| openfy.net | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| opensuite.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| netsuite.net | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| hubpoint.net | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| openworks.net | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| maxpoint.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| pivotaltracker.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| hubapp.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| syncsuite.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| smartforce.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| primesuite.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| primeio.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| primeio.io | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| yammer.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY | STALE_NO_RECENT_USE |
| coreapp.io | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| rapidly.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| flexdesk.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| smartbox.co | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| flowhub.co | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| syncspace.co | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| workspace.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| ultraforce.org | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| rapidsoft.tech | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| openworks.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| synclabs.org | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| ultraly.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| linkapp.ai | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| workspace.co | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| coreworks.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| syncsuite.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| easypoint.cloud | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| fastly.dev | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| primeio.org | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| zoom-legacy.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY | STALE_NO_RECENT_USE |
| fasttech.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP | STALE_NO_RECENT_USE |
| hipchat.com | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB | HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY | STALE_NO_RECENT_USE |

### Missed Zombies (False Negatives)

**2 assets missed by AOD - should have been Zombie**

#### `cloudhub.cloud`

**Headline:** AOD missed cloudhub.cloud as zombie - domain exists in AOD evidence but not used as canonical key

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD has evidence for cloudhub.cloud but did not normalize to domain key
- **RCA Hint:** `KEY_NORMALIZATION_MISMATCH`
- **Key Drift:** Yes - domain exists in AOD evidence but not used as canonical key
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, STALE_ACTIVITY`

#### `ultrahub.com`

**Headline:** AOD missed ultrahub.com as zombie - registered but no recent usage

- **Farm Detail:** Farm expected ZOMBIE because: HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB
- **AOD Detail:** AOD did not flag this asset
- **RCA Hint:** `STALE_NO_RECENT_USE`
- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, STALE_ACTIVITY`

### False Positive Zombies

**53 assets incorrectly classified as Zombie by AOD**

#### Farm Classification: `clean` (22 assets)

**`database.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`databox.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`primesync.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`syncflow.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`networks.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flowify.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`cloudpoint.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`fastflow.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`hubly.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, FINANCIALLY_ANCHORED`

**`smartapp.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`netforce.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`hubspace.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`easylabs.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`ultralabs.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`maxly.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, FINANCIALLY_ANCHORED`

**`linkfy.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flexbase.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`easydesk.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`hubdesk.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flowforce.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`hubly.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, FINANCIALLY_ANCHORED`

**`openflow.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_PASS, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, HAS_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

#### Farm Classification: `parked` (28 assets)

**`maxify.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flowflow.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`netapp.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_FINANCE, NO_CMDB, NO_ONGOING_FINANCE`

**`workbox.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`openlabs.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`netdesk.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_FINANCE, NO_CMDB, NO_ONGOING_FINANCE`

**`worklabs.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flexhub.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`openify.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`rapidtech.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`primetech.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_FINANCE, NO_CMDB, NO_ONGOING_FINANCE`

**`profy.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, FINANCIALLY_ANCHORED`

**`fastio.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`netpoint.net`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`rapiddesk.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_FINANCE, NO_CMDB, NO_ONGOING_FINANCE`

**`linkdesk.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flexsoft.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flowdock.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`flowlabs.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`netbase.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`rapidpoint.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`rapidify.org`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flexsync.dev`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`fastsoft.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`profy.tech`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `HAS_ONGOING_FINANCE, DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, HAS_CMDB, HAS_FINANCE, FINANCIALLY_ANCHORED`

**`smartio.io`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`flexsync.ai`**

- **Farm Reason Codes:** `HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_DISCOVERY, ANCHORED, NO_IDP, NO_FINANCE, HAS_CMDB, NO_ONGOING_FINANCE`

**`datasoft.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, STALE_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_FINANCE, NO_CMDB, NO_ONGOING_FINANCE`

#### Farm Classification: `shadow` (3 assets)

**`cloudify.cloud`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`cloudworks.com`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

**`cloudfy.app`**

- **Farm Reason Codes:** `HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY, HAS_SECURITY_ATTESTATION, HAS_VALIDATION, GOVERNANCE_TRINITY_FAIL, HAS_FINANCE, HAS_ONGOING_FINANCE, RECENT_ACTIVITY`
- **AOD Reason Codes:** `DISCOVERY_SOURCE_COUNT_LT_2, ZOMBIE_CLASSIFICATION, STALE_ACTIVITY, HAS_IDP, ANCHORED, HAS_DISCOVERY, NO_CMDB, HAS_FINANCE, NO_ONGOING_FINANCE`

---

## Admission Analysis

### Admission Metrics

- **Total Assets:** 1123
- **Matched:** 1118
- **Missed:** 5
- **False Positives:** 38
- **Accuracy:** 99.6%

### Cataloged Missed by AOD

**5 assets should have been cataloged but weren't**

| Asset | Farm Classification |
|-------|---------------------|
| apexlogic-h8kp.com | admitted |
| datadoghq.com | admitted |
| tiktok.com | admitted |
| cloudhub.cloud | admitted |
| ultrahub.com | admitted |

### Admission False Positives (Cataloged)

**29 assets AOD cataloged but Farm expected rejection**

These assets should have been rejected (not admitted) based on Farm's admission policy.

| Asset Key | Discovery Sources | Rejection Reason | Farm Reason Codes |
|-----------|-------------------|------------------|-------------------|
| `openify.io` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `rapidtech.cloud` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `netapp.cloud` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `primetech.io` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `profy.com` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `datadog.com` | 0 (none) | None | N/A |
| `maxify.ai` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `fastio.net` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `workbox.io` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `fastsoft.app` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `netpoint.net` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `rapiddesk.cloud` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `linkdesk.tech` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `flexsoft.tech` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `profy.tech` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `flowdock.com` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `openlabs.ai` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `netdesk.com` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `worklabs.com` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `flowlabs.io` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `smartio.io` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `flexsync.ai` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `flexhub.app` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `flowflow.dev` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `netbase.io` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `rapidpoint.com` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `rapidify.org` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `flexsync.dev` | 0 (none) | None | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `datasoft.cloud` | 0 (none) | None | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |

### Admission False Positives (Rejected)

**9 assets AOD rejected but Farm expected admission**

| Asset Key | Discovery Sources | Farm Reason Codes |
|-----------|-------------------|-------------------|
| `netlabs.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `apexlogic-h8kp.com` | 2 (cloud_api, network_scan) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `datadoghq.com` | 3 (cloud_api, dns, proxy) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `linklabs.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `tiktok.com` | 2 (dns, proxy) | HAS_DISCOVERY, NO_IDP, MISSING_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `corebase.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `datasoft.ai` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, NO_CMDB, MISSING_VISIBILITY... |
| `cloudhub.cloud` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY... |
| `ultrahub.com` | 0 (none) | HAS_DISCOVERY, HAS_IDP, HAS_CONTROL, HAS_CMDB, HAS_VISIBILITY... |

---

## Root Cause Analysis Summary

| RCA Hint | Count |
|----------|-------|
| KEY_NORMALIZATION_MISMATCH | 92 |
| FP_FROM_PARKED | 28 |
| FP_FROM_CLEAN | 22 |
| FP_FROM_SHADOW | 3 |
| UNGOVERNED_ACTIVE | 1 |
| UNKNOWN | 1 |
| STALE_NO_RECENT_USE | 1 |

---

## Recommendations

- **Key Normalization:** AOD has evidence for some assets but is not using the expected canonical keys. Review key normalization logic.
- **Shadow Detection:** 93 expected shadows not found. Check shadow classification rules.
- **Zombie Detection:** 2 expected zombies not found. Check zombie classification rules.

---

*Generated by AOS Farm Assessment Engine*