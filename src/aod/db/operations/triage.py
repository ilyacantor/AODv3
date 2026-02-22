"""Triage action operations for database."""

import uuid
from datetime import datetime
from typing import Optional

import asyncpg


class TriageOperations:
    """Operations for triage action records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def save_triage_action(
        self,
        tenant_id: str,
        run_id: str,
        item_id: str,
        item_type: str,
        action: str,
        state: str,
        owner: Optional[str] = None,
        defer_until: Optional[str] = None,
        ignore_reason: Optional[str] = None
    ) -> dict:
        """Save or update a triage action."""
        pool = await self._get_pool()
        now = datetime.utcnow().isoformat()
        action_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Check for existing action by (run_id, item_id) only - item_type is informational
            existing = await conn.fetchrow(
                "SELECT action_id FROM triage_actions WHERE run_id = $1 AND item_id = $2",
                run_id, item_id
            )

            if existing:
                # Update existing action, including item_type in case asset moved to different section
                action_id = existing["action_id"]
                await conn.execute(
                    """
                    UPDATE triage_actions SET
                        action = $1, state = $2, owner = $3, defer_until = $4,
                        ignore_reason = $5, item_type = $6, updated_at = $7
                    WHERE action_id = $8
                    """,
                    action, state, owner, defer_until, ignore_reason, item_type, now, action_id
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO triage_actions (
                        action_id, tenant_id, run_id, item_id, item_type,
                        action, state, owner, defer_until, ignore_reason,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    action_id, tenant_id, run_id, item_id, item_type,
                    action, state, owner, defer_until, ignore_reason, now, now
                )

        return {
            "action_id": action_id,
            "item_id": item_id,
            "item_type": item_type,
            "action": action,
            "state": state,
            "owner": owner,
            "defer_until": defer_until,
            "ignore_reason": ignore_reason,
            "updated_at": now
        }

    async def get_triage_actions_by_run(self, run_id: str) -> list[dict]:
        """Get all triage actions for a run."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM triage_actions WHERE run_id = $1 ORDER BY updated_at DESC",
                run_id
            )

        return [dict(row) for row in rows]

    async def delete_triage_action(self, run_id: str, item_id: str) -> bool:
        """Delete a triage action (revert/undo)."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM triage_actions WHERE run_id = $1 AND item_id = $2",
                run_id, item_id
            )

        return "DELETE" in result
