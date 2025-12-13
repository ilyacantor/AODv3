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
    db: Database
) -> PipelineResult:
    """
    Execute the full AOD discovery pipeline.
    
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
        
    Returns:
        PipelineResult with run log, assets, artifacts, and findings
    """
    run_id = data.get("meta", {}).get("run_id", f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
    tenant_id = data.get("meta", {}).get("tenant_id", "unknown")
    
    run_log = RunLog(
        run_id=run_id,
        tenant_id=tenant_id,
        status=RunStatus.RUNNING,
        started_at=datetime.utcnow(),
        input_meta=data.get("meta", {}),
        counts=RunCounts()
    )
    
    await db.create_run(run_log)
    
    try:
        snapshot = validate_snapshot(data)
        
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
        
        filtered_candidates, artifacts = handle_artifacts(candidates, tenant_id, run_id)
        run_log.counts.artifacts_recorded = len(artifacts)
        
        correlation_by_entity_id = {c.entity.entity_id: c for c in correlations}
        
        assets = []
        rejected_count = 0
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejected_count += 1
                continue
            
            admission_result = apply_admission_criteria(correlation, tenant_id, run_id)
            
            if admission_result.admitted and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                rejected_count += 1
        
        run_log.counts.assets_admitted = len(assets)
        run_log.counts.rejected = rejected_count
        
        findings = generate_findings(assets, correlations, indexes, tenant_id, run_id)
        run_log.counts.findings_generated = len(findings)
        
        for asset in assets:
            await db.create_asset(asset)
        
        for artifact in artifacts:
            await db.create_artifact(artifact)
        
        for finding in findings:
            await db.create_finding(finding)
        
        run_log.status = RunStatus.COMPLETED
        run_log.completed_at = datetime.utcnow()
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
        run_log.completed_at = datetime.utcnow()
        run_log.failure_reasons = [str(e)]
        await db.update_run(run_log)
        
        return PipelineResult(
            success=False,
            run_log=run_log,
            error=str(e)
        )
        
    except Exception as e:
        run_log.status = RunStatus.FAILED
        run_log.completed_at = datetime.utcnow()
        run_log.failure_reasons = [str(e)]
        await db.update_run(run_log)
        
        return PipelineResult(
            success=False,
            run_log=run_log,
            error=str(e)
        )
