"""Serialization and deserialization helpers for database records."""

import json
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg

from ..models.output_contracts import (
    Asset, AssetType, Environment, LensStatuses, LensCoverage, LensMatchDebug,
    AssetIdentifiers, ActivityEvidence, VendorHypothesis, ProvisioningStatus,
    Artifact, ArtifactType, Finding, FindingType, FindingCategory, Severity,
    Confidence, Materiality, TriagePriority, RunLog, RunStatus, RunCounts,
    SyncStatus, PipelineStageTimings, FabricPlaneTag, SORTagging
)


def deserialize_asset_row(row: asyncpg.Record) -> Asset:
    """
    Deserialize a database row into an Asset object.

    Centralized helper to avoid duplication between get_assets_by_run and get_asset_by_id.
    """
    activity_evidence_data = row.get("activity_evidence", "{}")
    vendor_hypothesis_data = row.get("vendor_hypothesis")
    lens_match_debug_data = row.get("lens_match_debug")
    fabric_plane_tag_data = row.get("fabric_plane_tag")
    sor_tagging_data = row.get("sor_tagging")

    vendor_hypothesis = None
    lens_match_debug = None
    fabric_plane_tag = None
    sor_tagging = None
    if vendor_hypothesis_data:
        vendor_hypothesis = VendorHypothesis.model_validate_json(vendor_hypothesis_data)
    if lens_match_debug_data:
        lens_match_debug = LensMatchDebug.model_validate_json(lens_match_debug_data)
    if fabric_plane_tag_data:
        fabric_plane_tag = FabricPlaneTag.model_validate_json(fabric_plane_tag_data)
    if sor_tagging_data:
        sor_tagging = SORTagging.model_validate_json(sor_tagging_data)

    prov_status_raw = row.get("provisioning_status", "quarantine")
    try:
        prov_status = ProvisioningStatus(prov_status_raw)
    except ValueError:
        prov_status = ProvisioningStatus.QUARANTINE

    return Asset(
        asset_id=UUID(row["asset_id"]),
        tenant_id=row["tenant_id"],
        aod_discovery_id=row["run_id"],
        name=row["name"],
        asset_type=AssetType(row["asset_type"]),
        identifiers=AssetIdentifiers.model_validate_json(row["identifiers"]),
        vendor=row["vendor"],
        vendor_hypothesis=vendor_hypothesis,
        environment=Environment(row["environment"]),
        evidence_refs=json.loads(row["evidence_refs"]),
        lens_status=LensStatuses.model_validate_json(row["lens_status"]),
        lens_coverage=LensCoverage.model_validate_json(row["lens_coverage"]),
        lens_match_debug=lens_match_debug,
        activity_evidence=ActivityEvidence.model_validate_json(activity_evidence_data) if activity_evidence_data else ActivityEvidence(),
        tags=json.loads(row["tags"]),
        admission_reason=row["admission_reason"],
        provisioning_status=prov_status,
        has_critical_gap=row.get("has_critical_gap", False),
        owner=row.get("owner"),
        discovery_sources=json.loads(row.get("discovery_sources", "[]")),
        fabric_plane_tag=fabric_plane_tag,
        sor_tagging=sor_tagging,
        created_at=datetime.fromisoformat(row["created_at"])
    )


def deserialize_artifact_row(row: asyncpg.Record) -> Artifact:
    """Deserialize a database row into an Artifact object."""
    return Artifact(
        artifact_id=UUID(row["artifact_id"]),
        tenant_id=row["tenant_id"],
        aod_discovery_id=row["run_id"],
        parent_asset_id=UUID(row["parent_asset_id"]) if row["parent_asset_id"] else None,
        name=row["name"],
        artifact_type=ArtifactType(row["artifact_type"]),
        source=row["source"],
        evidence_ref=row["evidence_ref"],
        created_at=datetime.fromisoformat(row["created_at"])
    )


def deserialize_finding_row(row: asyncpg.Record) -> Finding:
    """Deserialize a database row into a Finding object."""
    return Finding(
        finding_id=UUID(row["finding_id"]),
        asset_id=UUID(row["asset_id"]) if row["asset_id"] else None,
        tenant_id=row["tenant_id"],
        aod_discovery_id=row["run_id"],
        finding_type=FindingType(row["finding_type"]),
        category=FindingCategory(row["category"]) if row.get("category") else FindingCategory.GOVERNANCE_FINDING,
        severity=Severity(row["severity"]),
        explanation=row["explanation"],
        evidence_refs=json.loads(row["evidence_refs"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        confidence=Confidence(row["confidence"]) if row.get("confidence") else Confidence.MED,
        materiality=Materiality(row["materiality"]) if row.get("materiality") else Materiality.MED,
        triage_priority=TriagePriority(row["triage_priority"]) if row.get("triage_priority") else TriagePriority.P2,
        conflict_field=row.get("conflict_field")
    )


def deserialize_run_row(row: asyncpg.Record) -> RunLog:
    """Deserialize a database row into a RunLog object."""
    sync_status_val = row.get("sync_status", "not_applicable")
    sync_error_val = row.get("sync_error")
    stage_timings_data = row.get("stage_timings")
    policy_snapshot_data = row.get("policy_snapshot")

    return RunLog(
        aod_discovery_id=row["run_id"],
        tenant_id=row["tenant_id"],
        entity_id=row.get("entity_id"),
        status=RunStatus(row["status"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        input_meta=json.loads(row["input_meta"]),
        counts=RunCounts.model_validate_json(row["counts"]),
        stage_timings=PipelineStageTimings.model_validate_json(stage_timings_data) if stage_timings_data else None,
        failure_reasons=json.loads(row["failure_reasons"]),
        sync_status=SyncStatus(sync_status_val),
        sync_error=sync_error_val,
        policy_snapshot=json.loads(policy_snapshot_data) if policy_snapshot_data else None
    )


# Underscore alias for backwards compatibility
_deserialize_asset_row = deserialize_asset_row
