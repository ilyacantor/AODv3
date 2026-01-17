"""Serialization helpers for database records."""

import json
from datetime import datetime
from uuid import UUID

import asyncpg

from ..models.output_contracts import (
    Asset, AssetType, Environment, LensStatuses, LensCoverage, LensMatchDebug,
    AssetIdentifiers, ActivityEvidence, VendorHypothesis, ProvisioningStatus
)


def _deserialize_asset_row(row: asyncpg.Record) -> Asset:
    """Deserialize a database row into an Asset object.

    Centralized helper to avoid duplication between get_assets_by_run and get_asset_by_id.
    """
    activity_evidence_data = row.get("activity_evidence", "{}")
    vendor_hypothesis_data = row.get("vendor_hypothesis")
    lens_match_debug_data = row.get("lens_match_debug")

    vendor_hypothesis = None
    lens_match_debug = None
    if vendor_hypothesis_data:
        vendor_hypothesis = VendorHypothesis.model_validate_json(vendor_hypothesis_data)
    if lens_match_debug_data:
        lens_match_debug = LensMatchDebug.model_validate_json(lens_match_debug_data)

    prov_status_raw = row.get("provisioning_status", "quarantine")
    try:
        prov_status = ProvisioningStatus(prov_status_raw)
    except ValueError:
        prov_status = ProvisioningStatus.QUARANTINE

    return Asset(
        asset_id=UUID(row["asset_id"]),
        tenant_id=row["tenant_id"],
        run_id=row["run_id"],
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
        created_at=datetime.fromisoformat(row["created_at"])
    )
