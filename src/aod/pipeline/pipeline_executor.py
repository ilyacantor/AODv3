"""Pipeline Executor - Orchestrate all pipeline stages"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..models.input_contracts import Snapshot
from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts
)
from ..db.database import Database
from ..llm.fringe_integration import apply_fringe_resolution, LLMExplainability

from .validate_snapshot import validate_snapshot, ValidationError
from .normalize_observations import normalize_observations, CandidateEntity
from .build_plane_indexes import build_plane_indexes, PlaneIndexes
from .correlate_entities import correlate_entities_to_planes, CorrelationResult, MatchStatus
from .admission import apply_admission_criteria, AdmissionResult
from .artifact_handler import handle_artifacts
from .findings_engine import generate_findings
from .deterministic_ids import deterministic_uuid
from .aod_agent_reconcile import VENDOR_TO_DOMAIN
from ..llm.fringe_integration import apply_fringe_resolution

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

MAX_OBSERVATION_SAMPLES = 2000


def _get_rejection_key(candidate: CandidateEntity) -> str | None:
    """
    Extract canonical rejection key matching Farm's expectations.

    CRITICAL: This MUST match the exact logic of _extract_raw_domain() in
    aod_agent_reconcile.py to ensure rejected assets use the same keys as
    admitted assets. Any divergence causes KEY_NORMALIZATION_MISMATCH errors.

    TODO: Refactor to share code with _extract_raw_domain() to eliminate duplication.
    Consider extracting to a shared utility that works with both Asset and CandidateEntity.

    Priority order (matches _extract_raw_domain() exactly):
    1. Domain from candidate (preserves subdomains for host-level granularity)
    2. Name if it looks like a domain (TLD length heuristic: 2-4 chars, alphabetic)
    3. Direct vendor lookup using VENDOR_TO_DOMAIN
    4. Normalized name vendor lookup
    5. None (no forced fallback - let caller handle)
    """
    from .aod_agent_reconcile import _normalize_name_for_vendor_lookup

    # Priority 1: Domain (preserve subdomains, no normalization)
    if candidate.domain and "." in candidate.domain:
        return candidate.domain.lower().strip()

    # Priority 2: Name if it looks like a domain
    # Uses TLD LENGTH HEURISTIC (2-4 alphabetic chars) instead of hardcoded list
    # Handles .uk, .com, .tech, .cloud, and future TLDs robustly
    name = candidate.original_name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            return name

    # Priority 3: Direct vendor lookup
    if candidate.vendor and candidate.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = candidate.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]

    # Priority 4: Normalized name vendor lookup
    # Handles cases like "Slack Inc." -> "slack" -> "slack.com"
    normalized_name = _normalize_name_for_vendor_lookup(candidate.original_name)
    if normalized_name in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[normalized_name]

    # No match: Return None instead of forcing a fallback
    # Caller must decide how to handle (e.g., use entity_id, skip rejection, etc.)
    return None


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
    provenance: dict[str, Any] | None = None,
    enable_llm: bool = False
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
        enable_llm: Enable LLM fringe resolution for ambiguous/unknown assets (default: False)

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
    
    print(f"[PIPELINE] Creating run record {run_id}...", flush=True)
    await db.create_run(run_log)
    print(f"[PIPELINE] Run record created", flush=True)
    
    try:
        print(f"[PIPELINE] Validating snapshot...", flush=True)
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
        
        obs_samples = []
        for candidate in candidates[:MAX_OBSERVATION_SAMPLES]:
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
        
        indexes = build_plane_indexes(snapshot.planes)
        
        correlations = correlate_entities_to_planes(candidates, indexes)
        
        enable_llm = bool(provenance and provenance.get("enable_llm", False))
        print(f"[PIPELINE] LLM config: enable_llm={enable_llm}", flush=True)
        llm_resolution_count = 0
        llm_model_used: Optional[str] = None
        
        if enable_llm:
            import asyncio
            from ..llm.fringe_integration import should_trigger_fringe
            
            MAX_LLM_CANDIDATES = 5
            
            def needs_llm(c: CorrelationResult) -> bool:
                """Pre-filter: only process candidates that actually need LLM"""
                cmdb_matched = c.cmdb.status == MatchStatus.MATCHED
                idp_matched = c.idp.status == MatchStatus.MATCHED
                should_trigger, _ = should_trigger_fringe(
                    c.entity, cmdb_matched, idp_matched, None, None, True
                )
                return should_trigger
            
            all_candidates_for_llm = [c for c in correlations if needs_llm(c)]
            candidates_for_llm = all_candidates_for_llm[:MAX_LLM_CANDIDATES]
            print(f"[PIPELINE] LLM fringe: {len(candidates_for_llm)}/{len(all_candidates_for_llm)} candidates (max {MAX_LLM_CANDIDATES})", flush=True)
            
            results = [(c, LLMExplainability()) for c in correlations]
            
            if candidates_for_llm:
                processed_count = 0
                
                async def resolve_single(correlation: CorrelationResult) -> tuple[CorrelationResult, LLMExplainability]:
                    """Apply fringe resolution to a single correlation."""
                    nonlocal processed_count
                    try:
                        result = await apply_fringe_resolution(
                            entity_key=correlation.entity.entity_id,
                            tenant_id=tenant_id,
                            correlation_result=correlation,
                            db=db,
                            enable_llm=True
                        )
                        processed_count += 1
                        if processed_count % 10 == 0:
                            print(f"[PIPELINE] LLM progress: {processed_count}/{len(candidates_for_llm)}", flush=True)
                        return result
                    except Exception as e:
                        print(f"[PIPELINE] LLM error for {correlation.entity.entity_id}: {e}", flush=True)
                        return correlation, LLMExplainability()
                
                MAX_CONCURRENT = 10
                semaphore = asyncio.Semaphore(MAX_CONCURRENT)
                
                async def bounded_resolve(correlation: CorrelationResult) -> tuple[CorrelationResult, LLMExplainability]:
                    async with semaphore:
                        return await resolve_single(correlation)
                
                print(f"[PIPELINE] Starting LLM gather...", flush=True)
                llm_results = await asyncio.gather(*[bounded_resolve(c) for c in candidates_for_llm])
                print(f"[PIPELINE] LLM gather completed", flush=True)
                
                llm_result_map = {r[0].entity.entity_id: r for r in llm_results}
                print(f"[PIPELINE] Building result map...", flush=True)
                
                results = []
                for c in correlations:
                    if c.entity.entity_id in llm_result_map:
                        results.append(llm_result_map[c.entity.entity_id])
                    else:
                        results.append((c, LLMExplainability()))
                print(f"[PIPELINE] Result map built, processing {len(results)} results", flush=True)
            
            updated_correlations = []
            for updated_correlation, explainability in results:
                updated_correlations.append(updated_correlation)
                if explainability.llm_used:
                    llm_resolution_count += 1
                    if explainability.llm_model_id and not llm_model_used:
                        llm_model_used = f"{explainability.llm_provider}:{explainability.llm_model_id}"
            
            correlations = updated_correlations
            run_log.counts.llm_calls = llm_resolution_count
            run_log.counts.llm_model = llm_model_used
            print(f"[PIPELINE] LLM processing done: {llm_resolution_count} calls", flush=True)
        
        def is_finance_truly_ambiguous(plane_match) -> bool:
            """
            Finance is NOT ambiguous if all records are from the same vendor.
            A vendor with multiple transactions is EXPECTED, not ambiguous.
            True ambiguity = multiple DIFFERENT vendors matching.
            """
            if not plane_match.matched_records:
                return False
            
            vendor_names = set()
            for rec in plane_match.matched_records:
                if rec is None:
                    continue
                vendor_name = None
                if hasattr(rec, 'name'):
                    vendor_name = rec.name
                elif hasattr(rec, 'vendor_name'):
                    vendor_name = rec.vendor_name
                if vendor_name:
                    vendor_names.add(vendor_name.lower().strip())
            
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

        # Stage 4.5: LLM Fringe Resolution (optional)
        if enable_llm:
            logger.info(f"LLM fringe resolution enabled - processing {len(correlations)} entities")
            fringe_processed = 0
            fringe_resolved = 0
            updated_correlations = []

            for correlation in correlations:
                entity_key = correlation.entity.entity_id
                updated_correlation, explainability = await apply_fringe_resolution(
                    entity_key=entity_key,
                    tenant_id=tenant_id,
                    correlation_result=correlation,
                    db=db,
                    cmdb_candidates=None,
                    idp_candidates=None,
                    enable_llm=True,
                )
                updated_correlations.append(updated_correlation)

                if explainability.llm_used:
                    fringe_processed += 1
                    if explainability.fact_id:
                        fringe_resolved += 1

            correlations = updated_correlations
            logger.info(f"LLM fringe resolution: {fringe_processed} processed, {fringe_resolved} resolved")

        filtered_candidates, artifacts = handle_artifacts(candidates, tenant_id, run_id, snapshot_id)
        run_log.counts.artifacts_recorded = len(artifacts)
        
        correlation_by_entity_id = {c.entity.entity_id: c for c in correlations}
        
        assets = []
        rejections_batch = []
        
        for candidate in sorted(filtered_candidates, key=lambda c: c.entity_id):
            correlation = correlation_by_entity_id.get(candidate.entity_id)
            if not correlation:
                rejection_key = _get_rejection_key(candidate)
                if not rejection_key:
                    # No canonical key extractable - use normalized name as fallback
                    # This won't match Farm's expectations, but ensures rejection is recorded
                    import re
                    rejection_key = re.sub(r'[^a-z0-9]', '', candidate.original_name.lower()) or candidate.entity_id

                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
                rejections_batch.append((
                    rejection_id, run_id,
                    rejection_key,  # entity_key: canonical domain key (e.g., "dropboxusercontent.io")
                    rejection_key,  # entity_name: same as entity_key for consistency
                    "no_correlation", "Entity not found in correlation results",
                    json.dumps({
                        "source": candidate.source,
                        "domain": candidate.domain,
                        "original_name": candidate.original_name,
                        "original_entity_id": candidate.entity_id
                    }),
                    started_at.isoformat()
                ))
                continue
            
            entity_observations = [obs for obs in observations if obs.name == candidate.original_name or obs.domain == candidate.domain]
            admission_result = apply_admission_criteria(correlation, tenant_id, run_id, snapshot_id, entity_observations)
            
            if admission_result.admitted and admission_result.asset:
                assets.append(admission_result.asset)
            else:
                rejection_key = _get_rejection_key(candidate)
                if not rejection_key:
                    # No canonical key extractable - use normalized name as fallback
                    # This won't match Farm's expectations, but ensures rejection is recorded
                    import re
                    rejection_key = re.sub(r'[^a-z0-9]', '', candidate.original_name.lower()) or candidate.entity_id

                rejection_id = str(deterministic_uuid(snapshot_id, run_id, "rejection", candidate.entity_id))
                rejections_batch.append((
                    rejection_id, run_id,
                    rejection_key,  # entity_key: canonical domain key (e.g., "dropboxusercontent.io")
                    rejection_key,  # entity_name: same as entity_key for consistency
                    "admission_failed", admission_result.rejection_reason or "No admission criteria satisfied",
                    json.dumps({
                        "idp_status": correlation.idp.status.value,
                        "cmdb_status": correlation.cmdb.status.value,
                        "cloud_status": correlation.cloud.status.value,
                        "finance_status": correlation.finance.status.value,
                        "original_name": candidate.original_name,
                        "original_entity_id": candidate.entity_id
                    }),
                    started_at.isoformat()
                ))
        
        await db.create_rejections_batch(rejections_batch)
        run_log.counts.assets_admitted = len(assets)
        run_log.counts.rejected = len(rejections_batch)
        
        findings = generate_findings(assets, correlations, indexes, tenant_id, run_id, snapshot_id)
        run_log.counts.findings_generated = len(findings)
        
        await db.create_assets_batch(assets)
        await db.create_artifacts_batch(artifacts)
        await db.create_findings_batch(findings)
        
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
