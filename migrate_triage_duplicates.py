#!/usr/bin/env python3
"""
Migration script to remove duplicate triage actions.

This script handles the transition from allowing multiple triage actions
per (run_id, item_id, item_type) to enforcing a single action per (run_id, item_id).

For each set of duplicates, it keeps the most recently updated action and deletes the rest.
"""

import asyncio
import asyncpg
import os
from datetime import datetime


async def migrate_triage_duplicates():
    """Remove duplicate triage actions, keeping the most recent per (run_id, item_id)."""

    # Get database connection string from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return False

    print("Connecting to database...")
    conn = await asyncpg.connect(db_url)

    try:
        # Find all duplicate groups (same run_id and item_id)
        duplicates = await conn.fetch("""
            SELECT run_id, item_id, COUNT(*) as count
            FROM triage_actions
            GROUP BY run_id, item_id
            HAVING COUNT(*) > 1
        """)

        if not duplicates:
            print("✓ No duplicate triage actions found. Database is clean.")
            return True

        print(f"Found {len(duplicates)} sets of duplicate triage actions.")

        total_deleted = 0

        for dup in duplicates:
            run_id = dup['run_id']
            item_id = dup['item_id']
            count = dup['count']

            # Get all actions for this (run_id, item_id) ordered by updated_at DESC
            actions = await conn.fetch("""
                SELECT action_id, item_type, action, state, updated_at
                FROM triage_actions
                WHERE run_id = $1 AND item_id = $2
                ORDER BY updated_at DESC
            """, run_id, item_id)

            # Keep the first one (most recent), delete the rest
            keep_action = actions[0]
            delete_actions = actions[1:]

            print(f"\nRun: {run_id[:8]}... | Item: {item_id[:8]}... | Found {count} duplicates")
            print(f"  → Keeping: {keep_action['action']} ({keep_action['state']}) from {keep_action['updated_at']}")

            for action in delete_actions:
                print(f"  → Deleting: {action['action']} ({action['state']}) from {action['updated_at']}")
                await conn.execute(
                    "DELETE FROM triage_actions WHERE action_id = $1",
                    action['action_id']
                )
                total_deleted += 1

        print(f"\n✓ Migration complete. Deleted {total_deleted} duplicate triage actions.")
        print(f"✓ Kept {len(duplicates)} most recent actions (one per asset per run).")

        # Verify no duplicates remain
        remaining = await conn.fetchval("""
            SELECT COUNT(*)
            FROM (
                SELECT run_id, item_id, COUNT(*) as count
                FROM triage_actions
                GROUP BY run_id, item_id
                HAVING COUNT(*) > 1
            ) duplicates
        """)

        if remaining > 0:
            print(f"⚠ Warning: {remaining} duplicate sets still exist!")
            return False

        print("✓ Verified: No duplicates remain in database.")
        return True

    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Triage Actions Migration: Remove Duplicates")
    print("=" * 60)
    print()

    success = asyncio.run(migrate_triage_duplicates())

    if success:
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        exit(0)
    else:
        print("\n" + "=" * 60)
        print("Migration failed!")
        print("=" * 60)
        exit(1)
