"""Pipeline Executor - Orchestrate all pipeline stages"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

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
from .vendor_governance import propagate_vendor_governance
from .admission import apply_admission_criteria, AdmissionResult, build_idp_activity_map
from .artifact_handler import handle_artifacts
from .findings_engine import generate_findings
from .deterministic_ids import deterministic_uuid

logger = logging.getLogger(__name__)

MAX_OBSERVATION_SAMPLES = 2000


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
    observations: list[Observation]
) -> dict:
    """
    Build asset_data dict for PolicyEngine evaluation.
    
    Translates correlation results into the flat structure expected by PolicyEngine.
    """
    in_idp = correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    in_cmdb = correlation.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    in_cloud = correlation.cloud.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    in_finance = correlation.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    
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
    
    ci_type = ""
    lifecycle = ""
    for record in correlation.cmdb.matched_records:
        if hasattr(record, 'ci_type') and record.ci_type:
            ci_type = record.ci_type
        if hasattr(record, 'lifecycle') and record.lifecycle:
            lifecycle = record.lifecycle
    
    monthly_spend = 0.0
    for record in correlation.finance.matched_records:
        if hasattr(record, 'monthly_spend'):
            monthly_spend = max(monthly_spend, record.monthly_spend or 0)
        elif hasattr(record, 'amount'):
            monthly_spend = max(monthly_spend, record.amount or 0)
    
    from .admission import source_to_plane, DISCOVERY_CORROBORATION_PLANES
    
    discovery_planes = set()
    latest_observed_at: datetime | None = None
    for obs in observations:
        if obs.source:
            plane = source_to_plane(obs.source)
            if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
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
        "discovery_planes_count": len(discovery_planes),
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
    error: str = ""


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
        for candidate in candidates[:MAX_OBSERVATION_SAMPLES]:
            sample_id = str(deterministic_uuid(snapshot_id, run_id, "obs_sample", candidate.original_name, candidate.domain or ""))
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
        # Deduplicate by sample_id (first tuple element)
        seen_sample_ids = set()
        deduped_samples = []
        for row in obs_samples:
            if row[0] not in seen_sample_ids:
                seen_sample_ids.add(row[0])
                deduped_samples.append(row)
        await db.create_observation_samples_batch(deduped_samples)
        
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
                    
                    match_id = str(deterministic_uuid(snapshot_id, run_id, "ambiguous", c.entity.original_name, c.entity.domain or "", plane))
                    ambiguous_matches_batch.append((
                        match_id, run_id, c.entity.entity_id, c.entity.original_name, plane,
                        json.dumps(plane_match.matched_ids), json.dumps(candidate_names[:10]),
                        json.dumps([plane_match.match_method or "unknown"]), started_at.isoformat()
                    ))
        # Deduplicate by match_id (first tuple element) - keep first occurrence
        seen_ids = set()
        deduped_batch = []
        for row in ambiguous_matches_batch:
            if row[0] not in seen_ids:
                seen_ids.add(row[0])
                deduped_batch.append(row)
        await db.create_ambiguous_matches_batch(deduped_batch)
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
        
        if use_policy_engine:
            logger.info("policy_engine.primary_mode", extra={"run_id": run_id})
        
        t_start = time.perf_counter()
        assets = []
        rejections_batch = []
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.original_name, candidate.domain or ""))
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
                idp_activity_map=idp_activity_map
            )
            
            policy_asset_data = _build_policy_asset_data(candidate, correlation, entity_observations)
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
                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.original_name, candidate.domain or ""))
                rejections_batch.append((
                    rejection_id, run_id, candidate.entity_id, candidate.original_name,
                    "admission_failed", admission_result.rejection_reason or "No admission criteria satisfied",
                    json.dumps({
                        "idp_status": correlation.idp.status.value,
                        "cmdb_status": correlation.cmdb.status.value,
                        "cloud_status": correlation.cloud.status.value,
                        "finance_status": correlation.finance.status.value
                    }),
                    started_at.isoformat()
                ))
        
        # Deduplicate rejections by rejection_id (first tuple element)
        seen_rejection_ids = set()
        deduped_rejections = []
        for row in rejections_batch:
            if row[0] not in seen_rejection_ids:
                seen_rejection_ids.add(row[0])
                deduped_rejections.append(row)
        await db.create_rejections_batch(deduped_rejections)
        timings['admission'] = time.perf_counter() - t_start
        run_log.counts.assets_admitted = len(assets)
        run_log.counts.rejected = len(deduped_rejections)
        
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
