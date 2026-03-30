"""Asset tracing and decision debugging API routes"""

import uuid as uuid_lib

from fastapi import APIRouter, HTTPException

from ..schemas import (
    AssetTraceRequest,
    DomainTraceStep,
    AssetTraceResponse,
    TwoPathDiffRequest,
    PathDiffResult,
    TwoPathDiffResponse,
    DecisionTraceRequest,
    DecisionTraceResponse,
)
from ...db.database import get_db_direct


router = APIRouter(prefix="")


@router.post("/debug/trace-asset")
async def trace_asset(request: AssetTraceRequest) -> AssetTraceResponse:
    """
    Debug endpoint: Trace a single asset through the canonicalization pipeline.

    Shows:
    - Raw evidence domains extracted from observations
    - Canonicalization steps for each domain
    - Final asset key and where it was produced
    """
    from ...pipeline.vendor_inference import extract_registered_domain, DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN
    from ...pipeline.aod_agent_reconcile import _extract_registered_domain
    from ...utils.normalization import normalize_name_for_vendor_lookup as _normalize_name_for_vendor_lookup

    db = await get_db_direct()

    asset_row = await db.fetchrow(
        "SELECT * FROM assets WHERE run_id = $1 AND asset_id = $2",
        request.run_id, request.asset_key
    )

    if not asset_row:
        asset_row = await db.fetchrow(
            "SELECT * FROM assets WHERE run_id = $1 AND (name ILIKE $2 OR asset_id ILIKE $2)",
            request.run_id, f"%{request.asset_key}%"
        )

    obs_rows = await db.fetch(
        """SELECT * FROM observation_samples
           WHERE run_id = $1
           AND (name ILIKE $2 OR domain ILIKE $2 OR observation_id ILIKE $2)
           LIMIT 50""",
        request.run_id, f"%{request.asset_key}%"
    )

    raw_domains: list[str] = []
    observations: list[dict] = []

    for obs in obs_rows:
        obs_dict = dict(obs)
        observations.append(obs_dict)
        if obs_dict.get("domain"):
            raw_domains.append(obs_dict["domain"])
        name = obs_dict.get("name", "")
        if name and "." in name:
            parts = name.split(".")
            if len(parts) >= 2 and parts[-1] in ("com", "org", "net", "io", "co", "dev", "app", "us", "so"):
                raw_domains.append(name)

    canonicalization_steps: list[DomainTraceStep] = []

    for domain in set(raw_domains):
        registered = extract_registered_domain(domain)
        canonicalization_steps.append(DomainTraceStep(
            step="extract_registered_domain",
            input_value=domain,
            output_value=registered,
            function="extract_registered_domain",
            module="vendor_inference.py"
        ))

        if registered and registered in DOMAIN_TO_VENDOR:
            canonicalization_steps.append(DomainTraceStep(
                step="vendor_lookup",
                input_value=registered,
                output_value=DOMAIN_TO_VENDOR[registered],
                function="DOMAIN_TO_VENDOR lookup",
                module="vendor_inference.py"
            ))

    final_asset_key = None
    key_source = None
    asset_data = None

    if asset_row:
        asset_data = dict(asset_row)
        name = asset_data.get("name", "")
        identifiers = asset_data.get("identifiers", {})
        vendor = asset_data.get("vendor")

        domains_from_identifiers = identifiers.get("domains", []) if identifiers else []

        if domains_from_identifiers:
            domain = domains_from_identifiers[0]
            registered = extract_registered_domain(domain)
            final_asset_key = registered or domain
            key_source = "identifiers.domains"
            canonicalization_steps.append(DomainTraceStep(
                step="asset_key_from_identifiers",
                input_value=domain,
                output_value=final_asset_key,
                function="_extract_registered_domain",
                module="aod_agent_reconcile.py"
            ))
        elif "." in name:
            parts = name.split(".")
            if len(parts) >= 2 and parts[-1] in ("com", "org", "net", "io", "co", "dev", "app", "us", "so"):
                registered = extract_registered_domain(name)
                final_asset_key = registered or name
                key_source = "asset.name (domain-like)"
                canonicalization_steps.append(DomainTraceStep(
                    step="asset_key_from_name",
                    input_value=name,
                    output_value=final_asset_key,
                    function="_extract_registered_domain",
                    module="aod_agent_reconcile.py"
                ))
        elif vendor and vendor.lower() in VENDOR_TO_DOMAIN:
            final_asset_key = VENDOR_TO_DOMAIN[vendor.lower()]
            key_source = "vendor_to_domain_lookup"
            canonicalization_steps.append(DomainTraceStep(
                step="asset_key_from_vendor",
                input_value=vendor,
                output_value=final_asset_key,
                function="VENDOR_TO_DOMAIN lookup",
                module="aod_agent_reconcile.py"
            ))
        else:
            normalized = _normalize_name_for_vendor_lookup(name)
            if normalized in VENDOR_TO_DOMAIN:
                final_asset_key = VENDOR_TO_DOMAIN[normalized]
                key_source = "name_to_vendor_lookup"
                canonicalization_steps.append(DomainTraceStep(
                    step="asset_key_from_normalized_name",
                    input_value=name,
                    output_value=final_asset_key,
                    function="_normalize_name_for_vendor_lookup + VENDOR_TO_DOMAIN",
                    module="aod_agent_reconcile.py"
                ))
            else:
                final_asset_key = None
                key_source = "no_domain_available"

    return AssetTraceResponse(
        asset_key=request.asset_key,
        found_in_assets=bool(asset_row),
        found_in_observations=bool(obs_rows),
        raw_evidence_domains=list(set(raw_domains)),
        canonicalization_steps=canonicalization_steps,
        final_asset_key=final_asset_key,
        key_source=key_source,
        asset_data=asset_data,
        observations=observations
    )


@router.post("/debug/two-path-diff")
async def two_path_diff(request: TwoPathDiffRequest) -> TwoPathDiffResponse:
    """
    Debug endpoint: Compare canonicalization between vendor_inference and reconcile paths.

    Detects "two canonicalizers exist" bugs where different code paths
    produce different keys for the same input.
    """
    from ...pipeline.vendor_inference import extract_registered_domain as vendor_extract
    from ...pipeline.aod_agent_reconcile import _extract_registered_domain
    from ...models.output_contracts import Asset, AssetIdentifiers, LensStatuses, LensCoverage

    results: list[PathDiffResult] = []
    mismatches: list[str] = []

    for domain in request.domains:
        vendor_result = vendor_extract(domain)

        asset = Asset(
            asset_id=uuid_lib.uuid4(),
            tenant_id="test-tenant",
            run_id="test",
            name=domain,
            identifiers=AssetIdentifiers(domains=[]),
            vendor=None,
            lens_status=LensStatuses(),
            lens_coverage=LensCoverage(),
        )
        reconcile_result = _extract_registered_domain(asset)

        is_match = vendor_result == reconcile_result
        if not is_match:
            mismatches.append(f"{domain}: vendor={vendor_result}, reconcile={reconcile_result}")

        results.append(PathDiffResult(
            raw_domain=domain,
            vendor_inference_result=vendor_result,
            reconcile_result=reconcile_result,
            match=is_match
        ))

    return TwoPathDiffResponse(
        results=results,
        all_match=len(mismatches) == 0,
        mismatches=mismatches
    )


@router.post("/debug/decision-trace", response_model=DecisionTraceResponse)
async def get_decision_traces(request: DecisionTraceRequest):
    """
    Get decision traces for all assets in a run.

    This produces exactly 13 fields per asset for Farm/AOD comparison:
    - asset_key_used, registered_domain, raw_domains_seen
    - is_external, is_active, activity_window_days, activity_source, latest_activity_at
    - idp_present, cmdb_present, infra_excluded, is_shadow, reason_codes
    """
    from ...pipeline.decision_trace import compute_decision_trace, decision_traces_to_dict

    db = await get_db_direct()

    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")

    assets = await db.get_assets_by_run(request.run_id)

    traces = [compute_decision_trace(a, request.activity_window_days) for a in assets]
    traces_dict = decision_traces_to_dict(traces)

    fields = [
        "asset_key_used", "registered_domain", "raw_domains_seen",
        "is_external", "is_active", "activity_window_days", "activity_source",
        "latest_activity_at", "idp_present", "cmdb_present", "infra_excluded",
        "is_shadow", "reason_codes"
    ]

    return DecisionTraceResponse(
        aod_discovery_id=request.run_id,
        traces=traces_dict,
        count=len(traces),
        fields=fields
    )
