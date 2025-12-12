# AOD Defect Dictionary

This document defines all defects and findings that AOD Discover reports on during asset discovery and triage.

---

## Defect Categories

AOD classifies defects into two main categories:

| Category | Impact | Action Required |
|----------|--------|-----------------|
| **Blocking Issues** | Asset is PARKED | Human-in-the-loop (HITL) intervention required before cataloging |
| **Non-Blocking Findings** | Asset is CATALOGED | Review recommended but not blocking |

---

## Blocking Issues (PARKED)

These defects prevent an asset from being cataloged. Assets with blocking issues are placed in the PARKED state until resolved.

### SoR Conflict

| Field | Value |
|-------|-------|
| **Rule IDs** | `SOR_CONFLICT`, `ONT_SOR_CONFLICT` |
| **Display Name** | SoR Conflict |
| **Lifecycle State** | PARKED |
| **Description** | System of Record conflict detected - multiple authoritative sources disagree on asset attributes |
| **Resolution** | Identify the correct SoR and reconcile conflicting data |

### Schema Mismatch

| Field | Value |
|-------|-------|
| **Rule IDs** | `SCHEMA_MISMATCH`, `SCHEMA_OR_SHAPE_MISMATCH`, `DATA_SCHEMA_DRIFT`, `ONT_AMBIGUOUS_TYPE` |
| **Display Name** | Schema Mismatch |
| **Lifecycle State** | PARKED |
| **Description** | Asset schema does not match expected structure, or schema has drifted from baseline |
| **Resolution** | Validate asset schema against ontology and update mapping rules |

### ID Collision

| Field | Value |
|-------|-------|
| **Rule IDs** | `ID_COLLISION` |
| **Display Name** | ID Collision |
| **Lifecycle State** | PARKED |
| **Description** | Multiple assets share the same identifier, creating ambiguity |
| **Resolution** | De-duplicate assets or assign unique identifiers |

### Missing ID

| Field | Value |
|-------|-------|
| **Rule IDs** | `MISSING_PRIMARY_ID` |
| **Display Name** | Missing ID |
| **Lifecycle State** | PARKED |
| **Description** | Asset lacks a primary identifier required for cataloging |
| **Resolution** | Assign a valid primary identifier to the asset |

---

## Non-Blocking Findings (CATALOGED)

These findings are informational or advisory. Assets with these findings are still cataloged but flagged for review.

### Shadow IT

| Field | Value |
|-------|-------|
| **Rule ID** | `SHADOW_DETECTED` |
| **Finding Type** | `shadow_it` |
| **Severity** | `warn` |
| **Description** | Asset identified as Shadow IT - unauthorized or unmanaged application |
| **Trigger Conditions** | - `is_shadow_it` flag set by Farm, OR<br>- No ownership info AND no evidence in core lenses (IDP, CMDB, Billing) |
| **Evidence** | `is_shadow_it`, `reasons` (e.g., "no_idp_evidence", "no_cmdb_record") |
| **Business Impact** | Security risk, compliance gap, potential data exposure |

### Governance Gap

| Field | Value |
|-------|-------|
| **Rule ID** | `GOV_MISSING_INFO` |
| **Finding Type** | `governance_gap` |
| **Severity** | `warn` |
| **Description** | Asset has governance gaps requiring attention |
| **Trigger Conditions** | - No owner, owner_email, or owner_team defined, OR<br>- Vendor not in known taxonomy |
| **Evidence** | `reasons` (e.g., "No ownership information", "Unmapped vendor: Acme Corp") |
| **Business Impact** | Accountability unclear, vendor risk unassessed |

### Data Conflicts

| Field | Value |
|-------|-------|
| **Rule ID** | `DATA_CONFLICT_DETECTED` |
| **Finding Type** | `data_conflicts` |
| **Severity** | `warn` |
| **Description** | Data conflicts detected for this asset |
| **Trigger Conditions** | - `has_data_conflicts` flag is true, OR<br>- `conflict_types` array is non-empty |
| **Evidence** | `conflict_types` (e.g., ["field_mismatch", "schema_drift"]) |
| **Business Impact** | Data quality issues may affect downstream systems |

### Ops Risk

| Field | Value |
|-------|-------|
| **Rule ID** | `OPS_ANOMALY_HIGH` |
| **Finding Type** | `ops_risk` |
| **Severity** | `critical` (score >= 0.7) or `warn` (score >= 0.4) |
| **Description** | Operational risk detected based on anomaly scoring |
| **Trigger Conditions** | `anomaly_score >= 0.4` |
| **Evidence** | `anomaly_score` (float 0.0-1.0) |
| **Business Impact** | Potential operational issues, unusual behavior patterns |

### Low Confidence

| Field | Value |
|-------|-------|
| **Rule ID** | `LOW_CLASSIFICATION_CONFIDENCE` |
| **Finding Type** | `low_confidence` |
| **Severity** | `info` |
| **Description** | Low confidence in asset classification |
| **Trigger Conditions** | `prob_kind < 0.5` |
| **Evidence** | `prob_kind` (float 0.0-1.0) |
| **Business Impact** | Asset type may be misclassified, manual review recommended |

---

## Severity Levels

| Severity | Description | Action |
|----------|-------------|--------|
| `critical` | High-impact issue requiring immediate attention | Prioritize resolution |
| `warn` | Moderate issue that should be addressed | Review and remediate |
| `info` | Informational finding for awareness | Optional review |

---

## Farm Bucket Classification

Farm assigns each asset to exactly one mutually exclusive bucket:

| Bucket | Priority | Criteria |
|--------|----------|----------|
| `shadow` | 1 (highest) | `is_shadow_it = true` |
| `blocking` | 2 | Has blocking issue (PARKED state) |
| `non_blocking` | 3 | Has findings but not blocked |
| `clean` | 4 (lowest) | No issues detected |

---

## Quick Reference

### Blocking Rules Map

```
ONT_SOR_CONFLICT     → SoR Conflict
SOR_CONFLICT         → SoR Conflict
SCHEMA_MISMATCH      → Schema Mismatch
SCHEMA_OR_SHAPE_MISMATCH → Schema Mismatch
DATA_SCHEMA_DRIFT    → Schema Mismatch
ONT_AMBIGUOUS_TYPE   → Schema Mismatch
ID_COLLISION         → ID Collision
MISSING_PRIMARY_ID   → Missing ID
```

### Finding Types

```
shadow_it       → SHADOW_DETECTED
governance_gap  → GOV_MISSING_INFO
data_conflicts  → DATA_CONFLICT_DETECTED
ops_risk        → OPS_ANOMALY_HIGH
low_confidence  → LOW_CLASSIFICATION_CONFIDENCE
```
