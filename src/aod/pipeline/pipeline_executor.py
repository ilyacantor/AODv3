"""Pipeline Executor - Orchestrate all pipeline stages"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..models.input_contracts import Snapshot
from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts
)
from ..db.database import Database

from .validate_snapshot import validate_snapshot, ValidationError
from .normalize_observations import normalize_observations, CandidateEntity
from .build_plane_indexes import build_plane_indexes, PlaneIndexes
from .correlate_entities import correlate_entities_to_planes, CorrelationResult, MatchStatus
from .admission import apply_admission_criteria, AdmissionResult
from .artifact_handler import handle_artifacts
from .findings_engine import generate_findings
from .deterministic_ids import deterministic_uuid

MAX_OBSERVATION_SAMPLES = 2000


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
    
    try:
        snapshot = validate_snapshot(
            data,
            normalize=is_farm_source,
            fallback_tenant_id=fallback_tenant_id,
            snapshot_id=snapshot_id
        )
        
        observations = snapshot.planes.discovery.observations
        run_log.counts.observations_in = len(observations)
        
        candidates = normalize_observations(observations)
        run_log.counts.candidates_out = len(candidates)
        
        for i, candidate in enumerate(candidates[:MAX_OBSERVATION_SAMPLES]):
            sample_id = str(deterministic_uuid(snapshot_id, "obs_sample", candidate.entity_id))
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
            await db.create_observation_sample(
                sample_id=sample_id,
                run_id=run_id,
                name=candidate.original_name,
                domain=candidate.domain,
                source=candidate.source,
                category=None,
                raw_preview=raw_preview,
                created_at=started_at
            )
        
        indexes = build_plane_indexes(snapshot.planes)
        
        correlations = correlate_entities_to_planes(candidates, indexes)
        
        ambiguous_count = 0
        for c in correlations:
            planes_ambiguous = []
            if c.idp.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("idp")
            if c.cmdb.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("cmdb")
            if c.cloud.status == MatchStatus.AMBIGUOUS:
                planes_ambiguous.append("cloud")
            if c.finance.status == MatchStatus.AMBIGUOUS:
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
                    
                    match_id = str(deterministic_uuid(snapshot_id, "ambiguous", c.entity.entity_id, plane))
                    await db.create_ambiguous_match(
                        match_id=match_id,
                        run_id=run_id,
                        entity_key=c.entity.entity_id,
                        entity_name=c.entity.original_name,
                        plane=plane,
                        candidate_ids=plane_match.matched_ids,
                        candidate_names=candidate_names[:10],
                        match_keys=[plane_match.match_method or "unknown"],
                        created_at=started_at
                    )
        run_log.counts.ambiguous_matches = ambiguous_count
        
        filtered_candidates, artifacts = handle_artifacts(candidates, tenant_id, run_id, snapshot_id)
        run_log.counts.artifacts_recorded = len(artifacts)
        
        correlation_by_entity_id = {c.entity.entity_id: c for c in correlations}
        
        assets = []
        rejected_count = 0
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejected_count += 1
                rejection_id = str(deterministic_uuid(snapshot_id, "rejection", candidate.entity_id))
                await db.create_rejection(
                    rejection_id=rejection_id,
                    run_id=run_id,
                    entity_key=candidate.entity_id,
                    entity_name=candidate.original_name,
                    reason_code="no_correlation",
                    reason_detail="Entity not found in correlation results",
                    evidence_summary={"source": candidate.source, "domain": candidate.domain},
                    created_at=started_at
                )
                continue
            
            admission_result = apply_admission_criteria(correlation, tenant_id, run_id, snapshot_id)
            
            if admission_result.admitted and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                rejected_count += 1
                rejection_id = str(deterministic_uuid(snapshot_id, "rejection", candidate.entity_id))
                await db.create_rejection(
                    rejection_id=rejection_id,
                    run_id=run_id,
                    entity_key=candidate.entity_id,
                    entity_name=candidate.original_name,
                    reason_code="admission_failed",
                    reason_detail=admission_result.rejection_reason or "No admission criteria satisfied",
                    evidence_summary={
                        "idp_status": correlation.idp.status.value,
                        "cmdb_status": correlation.cmdb.status.value,
                        "cloud_status": correlation.cloud.status.value,
                        "finance_status": correlation.finance.status.value
                    },
                    created_at=started_at
                )
        
        run_log.counts.assets_admitted = len(assets)
        run_log.counts.rejected = rejected_count
        
        findings = generate_findings(assets, correlations, indexes, tenant_id, run_id, snapshot_id)
        run_log.counts.findings_generated = len(findings)
        
        for asset in assets:
            await db.create_asset(asset)
        
        for artifact in artifacts:
            await db.create_artifact(artifact)
        
        for finding in findings:
            await db.create_finding(finding)
        
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
