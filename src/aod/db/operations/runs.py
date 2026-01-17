"""Run log database operations.

Extracted from Database class - lines 381-512 of original database_old.py.
"""

import json
from datetime import datetime
from typing import Optional

from aod.models.output_contracts import RunLog, RunStatus, RunCounts, PipelineStageTimings, SyncStatus


async def create_run(pool, run: RunLog) -> RunLog:
    """Create a new run log entry"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO runs (run_id, tenant_id, status, started_at, completed_at, input_meta, counts, failure_reasons, sync_status, sync_error, stage_timings, policy_snapshot)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            run.run_id,
            run.tenant_id,
            run.status.value,
            run.started_at.isoformat(),
            run.completed_at.isoformat() if run.completed_at else None,
            json.dumps(run.input_meta),
            run.counts.model_dump_json(),
            json.dumps(run.failure_reasons),
            run.sync_status.value,
            run.sync_error,
            run.stage_timings.model_dump_json() if run.stage_timings else None,
            json.dumps(run.policy_snapshot) if run.policy_snapshot else None
        )
    return run


async def update_run(pool, run: RunLog) -> RunLog:
    """Update an existing run log entry"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE runs SET
                status = $1,
                completed_at = $2,
                counts = $3,
                failure_reasons = $4,
                sync_status = $5,
                sync_error = $6,
                stage_timings = $7,
                policy_snapshot = $8
            WHERE run_id = $9
            """,
            run.status.value,
            run.completed_at.isoformat() if run.completed_at else None,
            run.counts.model_dump_json(),
            json.dumps(run.failure_reasons),
            run.sync_status.value,
            run.sync_error,
            run.stage_timings.model_dump_json() if run.stage_timings else None,
            json.dumps(run.policy_snapshot) if run.policy_snapshot else None,
            run.run_id
        )
    return run


async def get_run(pool, run_id: str) -> Optional[RunLog]:
    """Get a run log entry by ID"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM runs WHERE run_id = $1",
            run_id
        )
    
    if not row:
        return None
    
    sync_status_val = row.get("sync_status", "not_applicable")
    sync_error_val = row.get("sync_error")
    stage_timings_data = row.get("stage_timings")
    policy_snapshot_data = row.get("policy_snapshot")
    
    return RunLog(
        run_id=row["run_id"],
        tenant_id=row["tenant_id"],
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


async def get_all_runs(pool) -> list[RunLog]:
    """Get all run logs"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM runs ORDER BY started_at DESC"
        )
    
    runs = []
    for row in rows:
        sync_status_val = row.get("sync_status", "not_applicable")
        sync_error_val = row.get("sync_error")
        stage_timings_data = row.get("stage_timings")
        policy_snapshot_data = row.get("policy_snapshot")
        runs.append(RunLog(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
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
        ))
    return runs


async def delete_all_runs(pool) -> int:
    """Delete all runs and associated data (assets, findings, etc.)"""
    async with pool.acquire() as conn:
        for table in ["triage_actions", "observation_samples", "derived_classifications", "llm_facts", "rejections", "ambiguous_matches", "artifacts", "findings", "assets"]:
            try:
                await conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        result = await conn.execute("DELETE FROM runs")
        deleted = int(result.split()[-1]) if result else 0
    return deleted
