"""Data conflict finding generation"""

from ...models.output_contracts import (
    Asset, Finding, FindingType, Severity, Confidence, Materiality
)
from ..correlate_entities import CorrelationResult, MatchStatus
from ..deterministic_ids import deterministic_uuid
from .base import get_category, compute_triage_priority, SECURITY_RELEVANT_FIELDS


def generate_data_conflict_findings(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> list[Finding]:
    """
    Generate data_conflict findings with TIGHTER GATE (Dec 2025):

    Trigger ONLY if:
    - Conflict is on a security-relevant field (owner, environment, lifecycle, etc.)
    - Conflict persists across trusted planes (CMDB vs IdP vs Cloud)
    - Dedupe by (asset, field_name) to avoid duplicate findings

    Returns one finding per conflicting field.
    """
    findings = []

    # Collect field values from each trusted plane (not discovery which is inference)
    field_values: dict[str, dict[str, set]] = {}  # field -> plane -> values

    for field_name in SECURITY_RELEVANT_FIELDS:
        field_values[field_name] = {}

        if correlation.cmdb.status == MatchStatus.MATCHED:
            for record in correlation.cmdb.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "cmdb" not in field_values[field_name]:
                            field_values[field_name]["cmdb"] = set()
                        field_values[field_name]["cmdb"].add(str(val).lower())

        if correlation.idp.status == MatchStatus.MATCHED:
            for record in correlation.idp.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "idp" not in field_values[field_name]:
                            field_values[field_name]["idp"] = set()
                        field_values[field_name]["idp"].add(str(val).lower())

        if correlation.cloud.status == MatchStatus.MATCHED:
            for record in correlation.cloud.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "cloud" not in field_values[field_name]:
                            field_values[field_name]["cloud"] = set()
                        field_values[field_name]["cloud"].add(str(val).lower())

    # Check each field for conflicts across trusted planes
    for field_name, plane_values in field_values.items():
        if len(plane_values) < 2:
            continue  # Need at least 2 planes to have conflict

        # Collect all unique values across planes
        all_values = set()
        sources_with_values = []
        for plane, values in plane_values.items():
            all_values.update(values)
            for v in values:
                sources_with_values.append(f"{plane.upper()}:{v}")

        if len(all_values) <= 1:
            continue  # No actual conflict

        # Determine priority based on field
        if field_name in ("owner", "business_owner"):
            confidence = Confidence.HIGH
            materiality = Materiality.HIGH
        elif field_name == "environment":
            confidence = Confidence.HIGH
            materiality = Materiality.MED
        else:
            confidence = Confidence.MED
            materiality = Materiality.MED

        triage = compute_triage_priority(confidence, materiality)

        findings.append(Finding(
            finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, f"data_conflict_{field_name}"),
            asset_id=asset.asset_id,
            tenant_id=tenant_id,
            run_id=run_id,
            finding_type=FindingType.DATA_CONFLICT,
            category=get_category(FindingType.DATA_CONFLICT),
            severity=Severity.MED,
            explanation=f"Asset '{asset.name}' has conflicting '{field_name}' values: {', '.join(sources_with_values)}",
            evidence_refs=asset.evidence_refs,
            confidence=confidence,
            materiality=materiality,
            triage_priority=triage,
            conflict_field=field_name
        ))

    return findings
