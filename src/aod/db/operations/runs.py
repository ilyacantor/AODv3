"""Run operations for database."""

import json
from typing import Optional

import asyncpg

from ...models.output_contracts import RunLog
from ..serializers import deserialize_run_row


class RunOperations:
    """Operations for run records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def create_run(self, run: RunLog) -> RunLog:
        """Create a new run log entry."""
        pool = await self._get_pool()

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

    async def update_run(self, run: RunLog) -> RunLog:
        """Update an existing run log entry."""
        pool = await self._get_pool()

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
                    policy_snapshot = $8,
                    input_meta = $9
                WHERE run_id = $10
                """,
                run.status.value,
                run.completed_at.isoformat() if run.completed_at else None,
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.sync_status.value,
                run.sync_error,
                run.stage_timings.model_dump_json() if run.stage_timings else None,
                json.dumps(run.policy_snapshot) if run.policy_snapshot else None,
                json.dumps(run.input_meta),
                run.run_id
            )
        return run

    async def get_run(self, run_id: str) -> Optional[RunLog]:
        """Get a run log entry by ID."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM runs WHERE run_id = $1",
                run_id
            )

        if not row:
            return None

        return deserialize_run_row(row)

    async def get_all_runs(self) -> list[RunLog]:
        """Get all run logs."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM runs ORDER BY started_at DESC"
            )

        return [deserialize_run_row(row) for row in rows]

    async def delete_all_runs(self) -> int:
        """Delete all runs and associated data (assets, findings, etc.)."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            for table in ["triage_actions", "observation_samples", "derived_classifications", "llm_facts", "rejections", "ambiguous_matches", "artifacts", "findings", "assets"]:
                try:
                    await conn.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            result = await conn.execute("DELETE FROM runs")
            deleted = int(result.split()[-1]) if result else 0
        return deleted
