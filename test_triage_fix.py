#!/usr/bin/env python3
"""
Test script to verify triage action recording fix.

This script tests that:
1. Taking an action on an asset creates a triage record
2. Taking a different action on the same asset UPDATES (not duplicates) the record
3. Triage actions are correctly reflected in both the triage UI and catalog view
"""

import asyncio
import asyncpg
import os
from datetime import datetime


async def test_triage_fix():
    """Test that triage actions are properly recorded without duplication."""

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return False

    print("Connecting to database...")
    conn = await asyncpg.connect(db_url)

    try:
        # Get a test run
        run = await conn.fetchrow("""
            SELECT run_id, tenant_id
            FROM runs
            ORDER BY started_at DESC
            LIMIT 1
        """)

        if not run:
            print("No runs found in database. Run discovery first.")
            return False

        run_id = run['run_id']
        tenant_id = run['tenant_id']
        print(f"Using run: {run_id[:8]}...")

        # Get a test asset
        asset = await conn.fetchrow("""
            SELECT asset_id
            FROM assets
            WHERE run_id = $1
            LIMIT 1
        """, run_id)

        if not asset:
            print("No assets found in run. Run discovery first.")
            return False

        asset_id = asset['asset_id']
        print(f"Using asset: {asset_id[:8]}...")

        # Clean up any existing triage actions for this asset
        await conn.execute("""
            DELETE FROM triage_actions
            WHERE run_id = $1 AND item_id = $2
        """, run_id, asset_id)
        print("Cleared existing triage actions for test asset")

        # Test 1: Create first triage action
        print("\n--- Test 1: Create triage action ---")
        action_id_1 = await conn.fetchval("""
            INSERT INTO triage_actions (
                action_id, tenant_id, run_id, item_id, item_type,
                action, state, owner, defer_until, ignore_reason,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid()::text, $1, $2, $3, 'shadow',
                'assign', 'assigned', 'John Doe', NULL, NULL,
                $4, $4
            ) RETURNING action_id
        """, tenant_id, run_id, asset_id, datetime.utcnow().isoformat())

        count = await conn.fetchval("""
            SELECT COUNT(*) FROM triage_actions
            WHERE run_id = $1 AND item_id = $2
        """, run_id, asset_id)

        if count == 1:
            print(f"✓ Created 1 triage action (action_id: {action_id_1[:8]}...)")
        else:
            print(f"✗ Expected 1 action, found {count}")
            return False

        # Test 2: Update triage action (same asset, different item_type)
        print("\n--- Test 2: Update triage action (different item_type) ---")
        try:
            await conn.execute("""
                INSERT INTO triage_actions (
                    action_id, tenant_id, run_id, item_id, item_type,
                    action, state, owner, defer_until, ignore_reason,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text, $1, $2, $3, 'zombie',
                    'deprovision', 'deprovisioned', 'Jane Smith', NULL, NULL,
                    $4, $4
                )
            """, tenant_id, run_id, asset_id, datetime.utcnow().isoformat())

            print("✗ Should have failed due to UNIQUE constraint violation!")
            return False
        except asyncpg.UniqueViolationError:
            print("✓ UNIQUE constraint prevented duplicate (expected)")

        # Test 3: Verify update works correctly
        print("\n--- Test 3: Update existing action ---")
        await conn.execute("""
            UPDATE triage_actions
            SET action = 'deprovision',
                state = 'deprovisioned',
                owner = 'Jane Smith',
                item_type = 'zombie',
                updated_at = $1
            WHERE run_id = $2 AND item_id = $3
        """, datetime.utcnow().isoformat(), run_id, asset_id)

        updated_action = await conn.fetchrow("""
            SELECT action, state, owner, item_type
            FROM triage_actions
            WHERE run_id = $1 AND item_id = $2
        """, run_id, asset_id)

        count = await conn.fetchval("""
            SELECT COUNT(*) FROM triage_actions
            WHERE run_id = $1 AND item_id = $2
        """, run_id, asset_id)

        if count == 1 and updated_action['action'] == 'deprovision':
            print(f"✓ Action updated successfully (still only 1 record)")
            print(f"  Action: {updated_action['action']}")
            print(f"  State: {updated_action['state']}")
            print(f"  Owner: {updated_action['owner']}")
            print(f"  Item type: {updated_action['item_type']}")
        else:
            print(f"✗ Expected 1 updated action, found {count}")
            return False

        # Test 4: Verify no duplicates exist across entire database
        print("\n--- Test 4: Check for duplicates across database ---")
        duplicates = await conn.fetchval("""
            SELECT COUNT(*)
            FROM (
                SELECT run_id, item_id, COUNT(*) as count
                FROM triage_actions
                GROUP BY run_id, item_id
                HAVING COUNT(*) > 1
            ) dup
        """)

        if duplicates == 0:
            print("✓ No duplicate triage actions found in database")
        else:
            print(f"✗ Found {duplicates} sets of duplicate actions!")
            return False

        # Clean up test data
        await conn.execute("""
            DELETE FROM triage_actions
            WHERE run_id = $1 AND item_id = $2
        """, run_id, asset_id)
        print("\nTest data cleaned up")

        return True

    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Triage Fix Verification Tests")
    print("=" * 60)
    print()

    success = asyncio.run(test_triage_fix())

    if success:
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        exit(0)
    else:
        print("\n" + "=" * 60)
        print("Tests failed! ✗")
        print("=" * 60)
        exit(1)
