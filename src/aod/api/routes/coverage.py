"""Timestamp coverage analysis API routes"""

import httpx
import os

from fastapi import APIRouter, HTTPException

from ..schemas import (
    TimestampCoverageRequest,
    PlaneCoverage,
    TimestampCoverageResponse,
)
from ..deps import get_farm_url


router = APIRouter(prefix="")


TIMESTAMP_FIELD_VARIANTS = {
    "discovery": ["observed_at", "observedAt", "timestamp", "ts", "created_at", "createdAt"],
    "idp": ["last_login_at", "lastLoginAt", "lastLogin", "last_activity", "lastActivity"],
    "cloud": ["observed_at", "observedAt", "timestamp", "ts", "created_at"],
    "finance_transactions": ["date", "datetime", "timestamp", "ts", "transaction_date", "transactionDate"],
    "endpoint_apps": ["last_seen_at", "lastSeenAt", "lastSeen", "observed_at"],
    "network_dns": ["timestamp", "observed_at", "observedAt", "ts"],
    "network_proxy": ["timestamp", "observed_at", "observedAt", "ts"],
}


@router.post("/debug/timestamp-coverage", response_model=TimestampCoverageResponse)
async def debug_timestamp_coverage(request: TimestampCoverageRequest):
    """
    Debug endpoint to analyze timestamp field coverage in raw vs normalized data.

    Compares what timestamp fields exist in the raw Farm snapshot payload
    vs what fields are present after normalization.
    """
    farm_url = get_farm_url() or "http://localhost:8000"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            url = f"{farm_url.rstrip('/')}/api/snapshots/{request.snapshot_id}"
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Farm error: {response.text}")
            raw_snapshot = response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Farm connection error: {str(e)}")

    from ...pipeline.farm_adapter import normalize_farm_snapshot
    from ...models.input_contracts import Snapshot

    normalized_dict = normalize_farm_snapshot(
        raw_snapshot,
        fallback_tenant_id=request.tenant_id,
        snapshot_id=request.snapshot_id
    )
    normalized = Snapshot.model_validate(normalized_dict)

    planes = raw_snapshot.get("planes", {})

    def analyze_plane(raw_records: list, normalized_records: list,
                      timestamp_variants: list[str], normalized_field: str) -> PlaneCoverage:
        raw_count = len(raw_records)
        raw_with_ts = 0
        raw_field_names_found: set[str] = set()
        examples_with: list[dict] = []
        examples_missing: list[dict] = []

        for rec in raw_records:
            if not isinstance(rec, dict):
                continue
            found_ts = False
            for variant in timestamp_variants:
                if rec.get(variant) is not None:
                    found_ts = True
                    raw_field_names_found.add(variant)

            if found_ts:
                raw_with_ts += 1
                if len(examples_with) < 3:
                    example = {"id": rec.get("observation_id") or rec.get("idp_id") or rec.get("txn_id") or rec.get("resource_id") or "?"}
                    for variant in timestamp_variants:
                        if rec.get(variant) is not None:
                            example[variant] = str(rec[variant])
                    examples_with.append(example)
            else:
                if len(examples_missing) < 3:
                    example = {"id": rec.get("observation_id") or rec.get("idp_id") or rec.get("txn_id") or rec.get("resource_id") or "?"}
                    example["fields_checked"] = timestamp_variants
                    examples_missing.append(example)

        normalized_with_ts = 0
        normalized_fields_used: set[str] = set()

        for rec in normalized_records:
            val = getattr(rec, normalized_field, None) if hasattr(rec, normalized_field) else None
            if val is not None:
                normalized_with_ts += 1
                normalized_fields_used.add(normalized_field)

        return PlaneCoverage(
            raw_count=raw_count,
            raw_with_timestamp=raw_with_ts,
            raw_timestamp_field_names_found=sorted(raw_field_names_found),
            normalized_with_timestamp=normalized_with_ts,
            normalized_timestamp_fields_used=sorted(normalized_fields_used),
            examples_with_timestamp=examples_with,
            examples_missing_timestamp=examples_missing
        )

    results: dict[str, PlaneCoverage] = {}

    discovery_raw = planes.get("discovery", {}).get("observations", [])
    results["discovery"] = analyze_plane(
        discovery_raw,
        normalized.planes.discovery.observations,
        TIMESTAMP_FIELD_VARIANTS["discovery"],
        "observed_at"
    )

    idp_raw = planes.get("idp", {}).get("objects", [])
    results["idp"] = analyze_plane(
        idp_raw,
        normalized.planes.idp.objects,
        TIMESTAMP_FIELD_VARIANTS["idp"],
        "last_login_at"
    )

    cloud_raw = planes.get("cloud", {}).get("resources", [])
    results["cloud"] = analyze_plane(
        cloud_raw,
        normalized.planes.cloud.resources,
        TIMESTAMP_FIELD_VARIANTS["cloud"],
        "observed_at"
    )

    finance_txns_raw = planes.get("finance", {}).get("transactions", [])
    results["finance_transactions"] = analyze_plane(
        finance_txns_raw,
        normalized.planes.finance.transactions,
        TIMESTAMP_FIELD_VARIANTS["finance_transactions"],
        "date"
    )

    endpoint_apps_raw = planes.get("endpoint", {}).get("installed_apps", [])
    results["endpoint_apps"] = analyze_plane(
        endpoint_apps_raw,
        normalized.planes.endpoint.installed_apps,
        TIMESTAMP_FIELD_VARIANTS["endpoint_apps"],
        "last_seen_at"
    )

    total_raw_with_ts = sum(p.raw_with_timestamp for p in results.values())
    total_raw_count = sum(p.raw_count for p in results.values())
    total_normalized_with_ts = sum(p.normalized_with_timestamp for p in results.values())

    if total_raw_with_ts == 0:
        conclusion = "TIMESTAMPS ABSENT UPSTREAM: Farm raw snapshot has 0 timestamp fields across all planes."
    elif total_normalized_with_ts == 0 and total_raw_with_ts > 0:
        conclusion = f"TIMESTAMPS DROPPED/MISMAPPED IN AOD: Raw has {total_raw_with_ts} timestamps, normalized has 0. Check field mapping."
    elif total_normalized_with_ts < total_raw_with_ts:
        conclusion = f"PARTIAL TIMESTAMP LOSS IN AOD: Raw has {total_raw_with_ts}, normalized has {total_normalized_with_ts}. Some fields not mapped."
    else:
        conclusion = f"TIMESTAMPS PRESERVED: Raw has {total_raw_with_ts}, normalized has {total_normalized_with_ts}."

    return TimestampCoverageResponse(
        snapshot_id=request.snapshot_id,
        run_id=request.run_id,
        planes=results,
        summary={
            "total_raw_records": total_raw_count,
            "total_raw_with_timestamp": total_raw_with_ts,
            "total_normalized_with_timestamp": total_normalized_with_ts,
            "timestamp_loss_count": total_raw_with_ts - total_normalized_with_ts
        },
        conclusion=conclusion
    )
