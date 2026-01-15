"""Pipeline Executor - Orchestrate all pipeline stages"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..models.input_contracts import Snapshot, Observation
from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts, PipelineStageTimings
)
from ..db.database import Database
from ..core.policy import PolicyEngine, get_current_config

from .validate_snapshot import validate_snapshot, ValidationError
from .normalize_observations import normalize_observations, CandidateEntity
from .build_plane_indexes import build_plane_indexes, PlaneIndexes
from .correlate_entities import correlate_entities_to_planes, CorrelationResult, MatchStatus
from .vendor_governance import (
    propagate_vendor_governance, 
    PropagatedGovernance,
    propagate_vendor_governance_farm_style
)
from .admission import (
    apply_admission_criteria, AdmissionResult, build_idp_activity_map,
    _extract_all_domains_from_correlation, _extract_domain_from_correlation,
    extract_cmdb_external_ref_domains
)
from .vendor_inference import extract_registered_domain
from .artifact_handler import handle_artifacts
from .findings_engine import generate_findings
from .deterministic_ids import deterministic_uuid
from .asset_identity import late_bind_and_merge_assets

logger = logging.getLogger(__name__)

# Note: MAX_OBSERVATION_SAMPLES removed - use get_current_config().query_limits.max_observation_samples


def _extract_plane_timestamps(correlation: 'CorrelationResult') -> list[datetime]:
    """
    Extract activity timestamps from correlated plane records.
    
    When discovery observations lack timestamps, we can use timestamps from
    governance plane records (IdP, CMDB, Cloud, Finance) to determine activity.
    
    IMPORTANT: Only use actual ACTIVITY fields, NOT created_at/updated_at which
    represent when the record was created/modified, not when the asset was used.
    
    Returns list of UTC-aware datetime objects from matched plane records.
    """
    timestamps = []
    
    planes = [
        (correlation.idp, ['last_login', 'last_access', 'last_activity']),
        (correlation.cmdb, ['last_seen']),
        (correlation.cloud, ['last_activity', 'last_access']),
        (correlation.finance, ['last_invoice_date', 'transaction_date']),
    ]
    
    for plane_match, timestamp_fields in planes:
        if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            for record in plane_match.matched_records:
                if record is None:
                    continue
                for field_name in timestamp_fields:
                    ts = getattr(record, field_name, None)
                    if ts is not None:
                        if isinstance(ts, datetime):
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            timestamps.append(ts)
                            break
                        elif isinstance(ts, str):
                            try:
                                parsed = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                if parsed.tzinfo is None:
                                    parsed = parsed.replace(tzinfo=timezone.utc)
                                timestamps.append(parsed)
                                break
                            except (ValueError, AttributeError):
                                continue
    
    return timestamps


def _build_policy_asset_data(
    candidate: CandidateEntity,
    correlation: CorrelationResult,
    observations: list[Observation],
    propagated_gov: Optional[PropagatedGovernance] = None
) -> dict:
    """
    Build asset_data dict for PolicyEngine evaluation.

    Translates correlation results into the flat structure expected by PolicyEngine.

    Includes vendor-propagated governance AND metadata in policy evaluation.

    Governance principle: only AUTHORITATIVE matches can assert governance.
    Heuristic matches (fuzzy, vendor, contains) provide enrichment but not governance.
    in_idp/in_cmdb now require both match existence AND authoritative match method.
    """
    # Governance requires AUTHORITATIVE match, not just any match
    # Heuristic matches (fuzzy, vendor, contains) are enrichment-only, cannot grant governance
    direct_idp = (
        correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
        and correlation.idp.is_authoritative
    )
    direct_cmdb = (
        correlation.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
        and correlation.cmdb.is_authoritative
    )
    propagated_idp = propagated_gov.idp_present if propagated_gov else False
    propagated_cmdb = propagated_gov.cmdb_present if propagated_gov else False
    in_idp = direct_idp or propagated_idp
    in_cmdb = direct_cmdb or propagated_cmdb
    in_cloud = correlation.cloud.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    in_finance = correlation.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)

    # Extract IdP metadata from direct matches
    has_sso = False
    has_scim = False
    is_service_principal = False
    for record in correlation.idp.matched_records:
        if hasattr(record, 'has_sso') and record.has_sso:
            has_sso = True
        if hasattr(record, 'has_scim') and record.has_scim:
            has_scim = True
        if hasattr(record, 'idp_type') and record.idp_type == "service_principal":
            is_service_principal = True

    # Jan 2026: If no direct IdP but has propagated IdP, use propagated metadata
    if not direct_idp and propagated_idp and propagated_gov:
        has_sso = propagated_gov.has_sso
        has_scim = propagated_gov.has_scim
        if propagated_gov.idp_type == "service_principal":
            is_service_principal = True

    # Extract CMDB metadata from direct matches
    ci_type = ""
    lifecycle = ""
    for record in correlation.cmdb.matched_records:
        if hasattr(record, 'ci_type') and record.ci_type:
            ci_type = record.ci_type
        if hasattr(record, 'lifecycle') and record.lifecycle:
            lifecycle = record.lifecycle

    # Jan 2026: If no direct CMDB but has propagated CMDB, use propagated metadata
    if not direct_cmdb and propagated_cmdb and propagated_gov:
        if propagated_gov.ci_type:
            ci_type = propagated_gov.ci_type
        if propagated_gov.lifecycle:
            lifecycle = propagated_gov.lifecycle
    
    monthly_spend = 0.0
    for record in correlation.finance.matched_records:
        if hasattr(record, 'monthly_spend'):
            monthly_spend = max(monthly_spend, record.monthly_spend or 0)
        elif hasattr(record, 'amount'):
            monthly_spend = max(monthly_spend, record.amount or 0)
    
    from .admission import source_to_plane, DISCOVERY_CORROBORATION_PLANES

    # Count SOURCES not PLANES for discovery admission
    # Farm's policy: dns + proxy = 2 sources (both network plane, but distinct sources)
    # This matches the admission.py logic that gates on source count, not plane diversity
    discovery_sources = set()
    discovery_planes = set()
    latest_observed_at: datetime | None = None
    for obs in observations:
        if obs.source:
            source_lower = obs.source.lower()
            plane = source_to_plane(source_lower)
            if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                discovery_sources.add(source_lower)
                discovery_planes.add(plane)
        if obs.observed_at:
            obs_ts = obs.observed_at if obs.observed_at.tzinfo else obs.observed_at.replace(tzinfo=timezone.utc)
            if latest_observed_at is None or obs_ts > latest_observed_at:
                latest_observed_at = obs_ts
    
    if latest_observed_at is None:
        plane_timestamps = _extract_plane_timestamps(correlation)
        if plane_timestamps:
            latest_observed_at = max(plane_timestamps)
    
    activity_window_days = 90
    if latest_observed_at is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=activity_window_days)
        is_active = latest_observed_at >= cutoff
    else:
        # No activity timestamps = INDETERMINATE, not stale
        # Design principle: "no evidence" ≠ "stale evidence"
        # Treat as active to prevent false positive zombie classification
        is_active = True
    
    return {
        "domain": candidate.domain or "",
        "in_idp": in_idp,
        "in_cmdb": in_cmdb,
        "in_cloud": in_cloud,
        "in_finance": in_finance,
        "has_sso": has_sso,
        "has_scim": has_scim,
        "is_service_principal": is_service_principal,
        "ci_type": ci_type,
        "lifecycle": lifecycle,
        "monthly_spend": monthly_spend,
        # Pass SOURCE count, not plane count
        # This ensures policy engine uses same metric as admission.py
        "discovery_source_count": len(discovery_sources),
        "is_active": is_active,
    }


@dataclass
class PipelineResult:
    """Result of pipeline execution"""
    success: bool
    run_log: RunLog
    assets: list[Asset] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    error: str = ""


@dataclass
class EphemeralPipelineResult:
    """Result of ephemeral pipeline execution (no database persistence)"""
    success: bool
    assets: list[Asset] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    snapshot_as_of: datetime | None = None
    error: str = ""
    stage1_metrics: dict[str, Any] = field(default_factory=dict)


def _compute_stage1_metrics(
    assets: list[Asset],
    correlation_by_entity_id: dict[str, 'CorrelationResult']
) -> dict[str, int]:
    """
    Compute Stage 1 metrics to verify CMDB external_ref domain injection is stopped.
    
    Stage 1 Fix: CMDB external_ref domains should go to reference_domains (enrichment),
    NOT to identifiers.domains (identity/admission).
    
    Metrics:
    - cmdb_external_ref_domains_extracted_total: Total domains extracted from CMDB external_ref
    - domains_added_to_identifiers_from_cmdb_external_ref_total: Should be 0 after Stage 1
    
    Returns:
        Dict with both metrics
    """
    cmdb_external_ref_domains_total = 0
    domains_in_identifiers_from_cmdb_total = 0
    
    for asset in assets:
        entity_id = None
        for evidence_ref in asset.evidence_refs:
            if evidence_ref.startswith("discovery:"):
                continue
            entity_id_candidate = evidence_ref.split(":")[-1] if ":" in evidence_ref else None
            if entity_id_candidate:
                entity_id = entity_id_candidate
                break
        
        correlation = None
        for eid, corr in correlation_by_entity_id.items():
            if corr.entity and corr.entity.canonical_name and asset.name:
                from .normalize_observations import normalize_string
                if normalize_string(corr.entity.canonical_name) == normalize_string(asset.name):
                    correlation = corr
                    break
        
        if not correlation:
            continue
        
        cmdb_external_ref_domains = extract_cmdb_external_ref_domains(correlation)
        cmdb_external_ref_domains_total += len(cmdb_external_ref_domains)
        
        if cmdb_external_ref_domains and asset.identifiers:
            asset_domains = set(d.lower() for d in (asset.identifiers.domains or []))
            for ext_domain in cmdb_external_ref_domains:
                registered = extract_registered_domain(ext_domain)
                if ext_domain.lower() in asset_domains or (registered and registered.lower() in asset_domains):
                    domains_in_identifiers_from_cmdb_total += 1
    
    return {
        "cmdb_external_ref_domains_extracted_total": cmdb_external_ref_domains_total,
        "domains_added_to_identifiers_from_cmdb_external_ref_total": domains_in_identifiers_from_cmdb_total
    }


def run_pipeline_ephemeral(
    data: dict[str, Any],
    run_id: str = "ephemeral_run",
    is_farm_source: bool = True
) -> EphemeralPipelineResult:
    """
    Run the AOD pipeline without database persistence.
    
    Useful for testing and reconciliation validation. Runs all compute stages
    but skips database writes, returning assets and rejections directly.
    
    Args:
        data: Raw snapshot JSON data
        run_id: Run identifier (defaults to "ephemeral_run")
        is_farm_source: Whether snapshot is from Farm (enables Farm format normalization)
    
    Returns:
        EphemeralPipelineResult with assets, rejections, findings
    """
    try:
        snapshot_id = data.get("meta", {}).get("snapshot_id", run_id)
        tenant_id = data.get("meta", {}).get("tenant_id", "unknown")
        started_at = datetime.now(timezone.utc)
        
        snapshot_as_of = None
        created_at_str = data.get("meta", {}).get("created_at") or data.get("meta", {}).get("generated_at")
        if created_at_str:
            try:
                snapshot_as_of = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if snapshot_as_of.tzinfo is None:
                    snapshot_as_of = snapshot_as_of.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
        
        snapshot = validate_snapshot(
            data,
            normalize=is_farm_source,
            fallback_tenant_id=tenant_id,
            snapshot_id=snapshot_id
        )
        
        observations = snapshot.planes.discovery.observations
        
        candidates, _ = normalize_observations(observations)
        
        indexes = build_plane_indexes(snapshot.planes)
        
        idp_activity_map = build_idp_activity_map(indexes.idp.records)
        
        correlations = correlate_entities_to_planes(candidates, indexes)
        
        filtered_candidates, artifacts = handle_artifacts(candidates, tenant_id, run_id, snapshot_id)
        
        correlation_by_entity_id = {c.entity.entity_id: c for c in correlations}
        
        propagated_governance = propagate_vendor_governance(correlations)
        
        policy_config = get_current_config()
        policy_engine = PolicyEngine(policy_config)
        use_policy_engine = policy_config.scope.use_policy_engine
        
        assets = []
        rejections = []
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejections.append({
                    "entity_key": candidate.entity_id,
                    "entity_name": candidate.original_name,
                    "reason_code": "no_correlation",
                    "reason_detail": "Entity not found in correlation results",
                    "evidence_summary": {"source": candidate.source, "domain": candidate.domain}
                })
                continue
            
            prop_gov = propagated_governance.get(candidate.entity_id)
            prop_idp = prop_gov.idp_present if prop_gov else False
            prop_cmdb = prop_gov.cmdb_present if prop_gov else False
            prop_reason = prop_gov.propagation_reason if prop_gov else None
            
            entity_observations = [obs for obs in observations if obs.observation_id in candidate.observation_ids]
            admission_result = apply_admission_criteria(
                correlation, tenant_id, run_id, snapshot_id, entity_observations,
                propagated_idp=prop_idp, propagated_cmdb=prop_cmdb, propagation_reason=prop_reason,
                idp_activity_map=idp_activity_map,
                snapshot_timestamp=snapshot_as_of
            )

            # Pass propagated governance with metadata to policy engine
            policy_asset_data = _build_policy_asset_data(
                candidate, correlation, entity_observations,
                propagated_gov=prop_gov
            )
            policy_decision = policy_engine.evaluate(policy_asset_data)

            should_admit = policy_decision.admitted if use_policy_engine else admission_result.admitted

            if should_admit and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                plane_domains = _extract_all_domains_from_correlation(correlation)
                rejection_domain = _extract_domain_from_correlation(correlation) or candidate.domain
                if not rejection_domain and plane_domains:
                    rejection_domain = plane_domains[0]
                rejection_registered_domain = extract_registered_domain(rejection_domain) if rejection_domain else None
                
                rejections.append({
                    "entity_key": candidate.entity_id,
                    "entity_name": candidate.original_name,
                    "reason_code": "admission_failed",
                    "reason_detail": admission_result.rejection_reason or "No admission criteria satisfied",
                    "domain": rejection_domain,
                    "registered_domain": rejection_registered_domain,
                    "evidence_summary": {
                        "idp_status": correlation.idp.status.value,
                        "cmdb_status": correlation.cmdb.status.value,
                        "cloud_status": correlation.cloud.status.value,
                        "finance_status": correlation.finance.status.value,
                        "domain": rejection_domain,
                        "registered_domain": rejection_registered_domain,
                        "domains": plane_domains,
                        "has_idp": correlation.idp.status.value in ("matched", "ambiguous"),
                        "has_cmdb": correlation.cmdb.status.value in ("matched", "ambiguous"),
                        "has_discovery": bool(candidate.observation_ids)
                    }
                })
        
        late_binding_enabled = policy_config.scope.late_binding_domain_merge
        assets = late_bind_and_merge_assets(assets, late_binding_enabled, logger)
        
        # Stage 3: Farm-style vendor governance propagation
        # Seeds from authoritative matches only (lens_coverage.idp/cmdb=True)
        # Propagates governance to all assets in the same vendor domain set
        assets = propagate_vendor_governance_farm_style(assets, logger)
        
        # Stage 1 Metrics: Track CMDB external_ref domain injection
        # cmdb_external_ref_domains_extracted_total: How many domains from CMDB external_ref
        # domains_added_to_identifiers_from_cmdb_external_ref_total: Should be 0 after Stage 1
        stage1_metrics = _compute_stage1_metrics(assets, correlation_by_entity_id)
        logger.info("stage1.cmdb_external_ref_metrics", extra={
            "run_id": run_id,
            "cmdb_external_ref_domains_extracted_total": stage1_metrics["cmdb_external_ref_domains_extracted_total"],
            "domains_added_to_identifiers_from_cmdb_external_ref_total": stage1_metrics["domains_added_to_identifiers_from_cmdb_external_ref_total"],
            "stage1_effective": stage1_metrics["domains_added_to_identifiers_from_cmdb_external_ref_total"] == 0
        })
        
        findings = generate_findings(assets, correlations, indexes, tenant_id, run_id, snapshot_id)
        
        return EphemeralPipelineResult(
            success=True,
            assets=assets,
            rejections=rejections,
            findings=findings,
            snapshot_as_of=snapshot_as_of,
            stage1_metrics=stage1_metrics
        )
        
    except ValidationError as e:
        return EphemeralPipelineResult(
            success=False,
            error=str(e)
        )
    except Exception as e:
        return EphemeralPipelineResult(
            success=False,
            error=str(e)
        )


async def execute_pipeline(
    data: dict[str, Any],
    db: Database,
    run_id: str,
    started_at: datetime,
    provenance: dict[str, Any] | None = None
) -> PipelineResult:
    """
    Execute the full AOD discovery pipeline.
    
    Pipeline computation is deterministic: same inputs produce same outputs.
    All identifiers and timestamps are provided from the API boundary.
    
    Stages:
    1. ValidateSnapshot - schema validate, reject banned fields
    2. NormalizeObservations - normalize names/domains, derive candidates
    3. BuildPlaneIndexes - build indexes for IdP/CMDB/Cloud/Finance
    4. CorrelateEntitiesToPlanes - three-pass matching
    5. Artifact Handling - filter out non-system objects
    6. Admission (AAC) - apply admission criteria
    7. Findings Engine - generate explainable findings
    8. Persist - write to database
    
    Args:
        data: Raw snapshot JSON data
        db: Database instance
        run_id: Unique run identifier (generated at API boundary)
        started_at: Run start timestamp (generated at API boundary)
        provenance: Optional provenance data for Farm runs (farm_url, snapshot_id, fetch_duration_ms, schema_version)
        
    Returns:
        PipelineResult with run log, assets, artifacts, and findings
    """
    is_farm_source = bool(provenance and provenance.get("source") == "farm")
    snapshot_id = str(provenance.get("snapshot_id")) if provenance and provenance.get("snapshot_id") else run_id
    fallback_tenant_id = data.get("meta", {}).get("tenant_id") or data.get("tenant_id")
    
    tenant_id = data.get("meta", {}).get("tenant_id", "unknown")
    
    snapshot_as_of = None
    created_at_str = data.get("meta", {}).get("created_at") or data.get("meta", {}).get("generated_at")
    if created_at_str:
        try:
            snapshot_as_of = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            if snapshot_as_of.tzinfo is None:
                snapshot_as_of = snapshot_as_of.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    
    input_meta = data.get("meta", {}).copy()
    if provenance:
        input_meta["provenance"] = provenance
    
    run_log = RunLog(
        run_id=run_id,
        tenant_id=tenant_id,
        status=RunStatus.RUNNING,
        started_at=started_at,
        input_meta=input_meta,
        counts=RunCounts()
    )
    
    await db.create_run(run_log)
    
    timings = {}
    
    if provenance and provenance.get("fetch_duration_ms"):
        timings['fetch_snapshot'] = provenance["fetch_duration_ms"] / 1000.0
    
    try:
        t_start = time.perf_counter()
        snapshot = validate_snapshot(
            data,
            normalize=is_farm_source,
            fallback_tenant_id=fallback_tenant_id,
            snapshot_id=snapshot_id
        )
        timings['validate_snapshot'] = time.perf_counter() - t_start
        
        observations = snapshot.planes.discovery.observations
        run_log.counts.observations_in = len(observations)
        
        t_start = time.perf_counter()
        candidates, iron_dome_rejections = normalize_observations(observations)
        timings['normalize'] = time.perf_counter() - t_start
        
        if iron_dome_rejections:
            logger.info("pipeline.iron_dome_rejections", extra={
                "run_id": run_id,
                "rejected_count": len(iron_dome_rejections),
                "sample_rejections": iron_dome_rejections[:5]
            })
            
            iron_dome_batch = []
            for rej in iron_dome_rejections:
                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "iron_dome", rej.get("observation_id", "")))
                iron_dome_batch.append((
                    rejection_id, run_id, rej.get("observation_id", ""), rej.get("name", ""),
                    "iron_dome", rej.get("reason", "Invalid key"),
                    json.dumps({"domain": rej.get("domain")}),
                    started_at.isoformat()
                ))
            await db.create_rejections_batch(iron_dome_batch)
        
        obs_samples = []
        max_samples = get_current_config().query_limits.max_observation_samples
        for candidate in candidates[:max_samples]:
            sample_id = str(deterministic_uuid(snapshot_id, run_id, "obs_sample", candidate.entity_id))
            raw_data = {
                "entity_id": candidate.entity_id,
                "canonical_name": candidate.canonical_name,
                "original_name": candidate.original_name,
                "domain": candidate.domain,
                "hostname": candidate.hostname,
                "uri": candidate.uri,
                "vendor": candidate.vendor,
                "source": candidate.source
            }
            raw_preview = json.dumps(raw_data)[:500]
            obs_samples.append((
                sample_id, run_id, candidate.original_name, candidate.domain,
                candidate.source, None, raw_preview, started_at.isoformat()
            ))
        await db.create_observation_samples_batch(obs_samples)
        
        t_start = time.perf_counter()
        indexes = build_plane_indexes(snapshot.planes)
        timings['build_indexes'] = time.perf_counter() - t_start
        
        # Jan 2026: Pre-compute IdP activity map for cross-IdP activity aggregation
        # This enables assets matched to IdP records with no last_login_at to inherit
        # activity from sibling IdP records with the same vendor/name
        idp_activity_map = build_idp_activity_map(indexes.idp.records)
        
        t_start = time.perf_counter()
        correlations = correlate_entities_to_planes(candidates, indexes)
        timings['correlate'] = time.perf_counter() - t_start
        
        def is_finance_truly_ambiguous(plane_match) -> bool:
            """
            Finance is NOT ambiguous if all records are from the same vendor.
            A vendor with multiple transactions is EXPECTED, not ambiguous.
            True ambiguity = multiple DIFFERENT vendors matching.
            """
            if not plane_match.matched_records:
                return False

            # Optimized: use set comprehension with generator expression
            vendor_names = {
                (rec.name if hasattr(rec, 'name') else rec.vendor_name).lower().strip()
                for rec in plane_match.matched_records
                if rec is not None and (hasattr(rec, 'name') or hasattr(rec, 'vendor_name'))
                and (rec.name if hasattr(rec, 'name') else getattr(rec, 'vendor_name', None))
            }

            return len(vendor_names) > 1
        
        ambiguous_count = 0
        ambiguous_matches_batch = []
        for c in correlations:
            planes_ambiguous = []
            if c.idp.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("idp")
            if c.cmdb.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("cmdb")
            if c.cloud.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("cloud")
            if c.finance.status == MatchStatus.AMBIGUOUS:
                if is_finance_truly_ambiguous(c.finance):
                    planes_ambiguous.append("finance")
            
            if planes_ambiguous:
                ambiguous_count += 1
                for plane in planes_ambiguous:
                    plane_match = getattr(c, plane)
                    candidate_names = []
                    for rec in plane_match.matched_records:
                        if hasattr(rec, 'name'):
                            candidate_names.append(rec.name)
                        elif hasattr(rec, 'canonical_name'):
                            candidate_names.append(rec.canonical_name)
                        else:
                            candidate_names.append(str(rec))
                    
                    match_id = str(deterministic_uuid(snapshot_id, run_id, "ambiguous", c.entity.entity_id, plane))
                    ambiguous_matches_batch.append((
                        match_id, run_id, c.entity.entity_id, c.entity.original_name, plane,
                        json.dumps(plane_match.matched_ids), json.dumps(candidate_names[:10]),
                        json.dumps([plane_match.match_method or "unknown"]), started_at.isoformat()
                    ))
        await db.create_ambiguous_matches_batch(ambiguous_matches_batch)
        run_log.counts.ambiguous_matches = ambiguous_count
        
        t_start = time.perf_counter()
        filtered_candidates, artifacts = handle_artifacts(candidates, tenant_id, run_id, snapshot_id)
        timings['artifacts'] = time.perf_counter() - t_start
        run_log.counts.artifacts_recorded = len(artifacts)
        run_log.counts.candidates_out = len(filtered_candidates)
        
        correlation_by_entity_id = {c.entity.entity_id: c for c in correlations}
        
        propagated_governance = propagate_vendor_governance(correlations)
        
        policy_config = get_current_config()
        policy_engine = PolicyEngine(policy_config)
        use_policy_engine = policy_config.scope.use_policy_engine
        policy_mismatches = []
        
        run_log.policy_snapshot = policy_config.to_dict()
        
        if use_policy_engine:
            logger.info("policy_engine.primary_mode", extra={"run_id": run_id})
        
        t_start = time.perf_counter()
        assets = []
        rejections_batch = []
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
                rejections_batch.append((
                    rejection_id, run_id, candidate.entity_id, candidate.original_name,
                    "no_correlation", "Entity not found in correlation results",
                    json.dumps({"source": candidate.source, "domain": candidate.domain}),
                    started_at.isoformat()
                ))
                continue
            
            prop_gov = propagated_governance.get(candidate.entity_id)
            prop_idp = prop_gov.idp_present if prop_gov else False
            prop_cmdb = prop_gov.cmdb_present if prop_gov else False
            prop_reason = prop_gov.propagation_reason if prop_gov else None
            
            entity_observations = [obs for obs in observations if obs.observation_id in candidate.observation_ids]
            admission_result = apply_admission_criteria(
                correlation, tenant_id, run_id, snapshot_id, entity_observations,
                propagated_idp=prop_idp, propagated_cmdb=prop_cmdb, propagation_reason=prop_reason,
                idp_activity_map=idp_activity_map,
                snapshot_timestamp=snapshot_as_of
            )

            # Pass propagated governance with metadata to policy engine
            policy_asset_data = _build_policy_asset_data(
                candidate, correlation, entity_observations,
                propagated_gov=prop_gov
            )
            policy_decision = policy_engine.evaluate(policy_asset_data)
            
            if admission_result.admitted != policy_decision.admitted:
                policy_mismatches.append({
                    "entity": candidate.original_name,
                    "domain": candidate.domain,
                    "legacy_admitted": admission_result.admitted,
                    "policy_admitted": policy_decision.admitted,
                    "legacy_reason": admission_result.rejection_reason or admission_result.admission_reason,
                    "policy_reason": policy_decision.rejection_reason or policy_decision.admission_reason,
                    "policy_codes": policy_decision.reason_codes,
                    "asset_data": policy_asset_data,
                })
            
            should_admit = policy_decision.admitted if use_policy_engine else admission_result.admitted
            
            if should_admit and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
                # Include plane-extracted domains in rejection evidence
                # This enables alias_keys building for rejected assets so Farm can match them
                plane_domains = _extract_all_domains_from_correlation(correlation)
                # Compute proper registered domain (eTLD+1), not raw FQDN
                # Priority: correlation-recovered domain > candidate domain > first plane domain
                # CRITICAL: Always populate domain to avoid downstream null checks
                rejection_domain = None
                recovered_domain = _extract_domain_from_correlation(correlation)
                if recovered_domain:
                    rejection_domain = recovered_domain
                elif candidate.domain:
                    rejection_domain = candidate.domain
                elif plane_domains:
                    rejection_domain = plane_domains[0]
                # Compute registered domain (eTLD+1)
                rejection_registered_domain = None
                if rejection_domain:
                    rejection_registered_domain = extract_registered_domain(rejection_domain)
                elif plane_domains:
                    rejection_registered_domain = extract_registered_domain(plane_domains[0])
                    rejection_domain = plane_domains[0]
                rejections_batch.append((
                    rejection_id, run_id, candidate.entity_id, candidate.original_name,
                    "admission_failed", admission_result.rejection_reason or "No admission criteria satisfied",
                    json.dumps({
                        "idp_status": correlation.idp.status.value,
                        "cmdb_status": correlation.cmdb.status.value,
                        "cloud_status": correlation.cloud.status.value,
                        "finance_status": correlation.finance.status.value,
                        "domain": rejection_domain,
                        "registered_domain": rejection_registered_domain,
                        "domains": plane_domains,
                        "has_idp": correlation.idp.status.value in ("matched", "ambiguous"),
                        "has_cmdb": correlation.cmdb.status.value in ("matched", "ambiguous"),
                        "has_discovery": bool(candidate.observation_ids)
                    }),
                    started_at.isoformat()
                ))
        
        await db.create_rejections_batch(rejections_batch)
        timings['admission'] = time.perf_counter() - t_start
        run_log.counts.assets_admitted = len(assets)
        run_log.counts.rejected = len(rejections_batch)
        
        t_start = time.perf_counter()
        late_binding_enabled = policy_config.scope.late_binding_domain_merge
        pre_merge_count = len(assets)
        assets = late_bind_and_merge_assets(assets, late_binding_enabled, logger)
        timings['domain_merge'] = time.perf_counter() - t_start
        
        if late_binding_enabled:
            post_merge_count = len(assets)
            run_log.counts.assets_admitted = post_merge_count
            if post_merge_count != pre_merge_count:
                logger.info("pipeline.domain_merge_applied", extra={
                    "run_id": run_id,
                    "pre_merge_count": pre_merge_count,
                    "post_merge_count": post_merge_count,
                    "merged_count": pre_merge_count - post_merge_count
                })
        
        # Stage 3: Farm-style vendor governance propagation
        # Seeds from authoritative matches only (lens_coverage.idp/cmdb=True)
        # Propagates governance to all assets in the same vendor domain set
        t_start = time.perf_counter()
        assets = propagate_vendor_governance_farm_style(assets, logger)
        timings['vendor_governance'] = time.perf_counter() - t_start
        
        # Stage 1 Metrics: Track CMDB external_ref domain injection
        stage1_metrics = _compute_stage1_metrics(assets, correlation_by_entity_id)
        logger.info("stage1.cmdb_external_ref_metrics", extra={
            "run_id": run_id,
            "cmdb_external_ref_domains_extracted_total": stage1_metrics["cmdb_external_ref_domains_extracted_total"],
            "domains_added_to_identifiers_from_cmdb_external_ref_total": stage1_metrics["domains_added_to_identifiers_from_cmdb_external_ref_total"],
            "stage1_effective": stage1_metrics["domains_added_to_identifiers_from_cmdb_external_ref_total"] == 0
        })
        
        if policy_mismatches:
            logger.warning("policy_engine.mismatch_detected", extra={
                "run_id": run_id,
                "mismatch_count": len(policy_mismatches),
                "mismatches": policy_mismatches[:10],
            })
        else:
            logger.info("policy_engine.validation_passed", extra={
                "run_id": run_id,
                "candidates_evaluated": len(filtered_candidates),
            })
        
        t_start = time.perf_counter()
        findings = generate_findings(assets, correlations, indexes, tenant_id, run_id, snapshot_id)
        timings['findings'] = time.perf_counter() - t_start
        run_log.counts.findings_generated = len(findings)
        
        t_start = time.perf_counter()
        await db.create_assets_batch(assets)
        await db.create_artifacts_batch(artifacts)
        await db.create_findings_batch(findings)
        timings['persist'] = time.perf_counter() - t_start
        
        timings['total'] = sum(timings.values())
        run_log.stage_timings = PipelineStageTimings(**timings)
        
        if len(assets) > 0:
            run_log.status = RunStatus.COMPLETED_WITH_RESULTS
        else:
            run_log.status = RunStatus.COMPLETED_NO_ASSETS
        run_log.completed_at = started_at
        await db.update_run(run_log)
        
        return PipelineResult(
            success=True,
            run_log=run_log,
            assets=assets,
            artifacts=artifacts,
            findings=findings
        )
        
    except ValidationError as e:
        run_log.status = RunStatus.INVALID_INPUT_CONTRACT
        run_log.completed_at = started_at
        run_log.failure_reasons = [str(e)]
        await db.update_run(run_log)
        
        return PipelineResult(
            success=False,
            run_log=run_log,
            error=str(e)
        )
        
    except Exception as e:
        run_log.status = RunStatus.FAILED
        run_log.completed_at = started_at
        run_log.failure_reasons = [str(e)]
        await db.update_run(run_log)
        
        return PipelineResult(
            success=False,
            run_log=run_log,
            error=str(e)
        )
