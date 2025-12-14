"""Pipeline Executor - Orchestrate all pipeline stages"""

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
        
        indexes = build_plane_indexes(snapshot.planes)
        
        correlations = correlate_entities_to_planes(candidates, indexes)
        
        ambiguous_count = sum(
            1 for c in correlations
            if any([
                c.idp.status == MatchStatus.AMBIGUOUS,
                c.cmdb.status == MatchStatus.AMBIGUOUS,
                c.cloud.status == MatchStatus.AMBIGUOUS,
                c.finance.status == MatchStatus.AMBIGUOUS
            ])
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
                continue
            
            admission_result = apply_admission_criteria(correlation, tenant_id, run_id, snapshot_id)
            
            if admission_result.admitted and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                rejected_count += 1
        
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
