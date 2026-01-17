"""Triage action database operations.

Extracted from Database class - lines 1192-1274 of original database_old.py.
"""

import uuid
from datetime import datetime
from typing import Optional


async def save_triage_action(
    pool, 
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
    """Save or update a triage action"""
    now = datetime.utcnow().isoformat()
    action_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT action_id FROM triage_actions WHERE run_id = $1 AND item_id = $2 AND item_type = $3",
            run_id, item_id, item_type
        )
        
        if existing:
            action_id = existing["action_id"]
            await conn.execute(
                """
                UPDATE triage_actions SET 
                    action = $1, state = $2, owner = $3, defer_until = $4, 
                    ignore_reason = $5, updated_at = $6
                WHERE action_id = $7
                """,
                action, state, owner, defer_until, ignore_reason, now, action_id
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


async def get_triage_actions_by_run(pool, run_id: str) -> list[dict]:
    """Get all triage actions for a run"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM triage_actions WHERE run_id = $1 ORDER BY updated_at DESC",
            run_id
        )
    
    return [dict(row) for row in rows]


async def delete_triage_action(pool, run_id: str, item_id: str) -> bool:
    """Delete a triage action (revert/undo)"""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM triage_actions WHERE run_id = $1 AND item_id = $2",
            run_id, item_id
        )
    
    return "DELETE" in result
