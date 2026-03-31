"""Regression test: run-scoped IDs prevent overwrites when re-running same snapshot"""

import pytest
import json
from datetime import datetime
from uuid import UUID, uuid4
import copy

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.db.database import Database
from aod.pipeline.pipeline_executor import execute_pipeline


MINIMAL_SNAPSHOT = {
    "meta": {
        "snapshot_id": "test-snapshot-run-scoped",
        "schema_version": "1.0",
        "tenant_id": "test-tenant",
        "run_id": "placeholder",
        "generated_at": "2024-01-15T10:00:00Z"
    },
    "planes": {
        "discovery": {
            "observations": [
                {
                    "observation_id": "obs-1",
                    "name": "Salesforce",
                    "domain": "salesforce.com",
                    "source": "network_dns"
                },
                {
                    "observation_id": "obs-2",
                    "name": "Slack",
                    "domain": "slack.com",
                    "source": "network_proxy"
                }
            ]
        },
        "idp": {
            "objects": [
                {
                    "idp_id": "idp-1",
                    "name": "Salesforce CRM"
                }
            ]
        },
        "cmdb": {"cis": []},
        "cloud": {"resources": []},
        "endpoint": {"devices": [], "installed_apps": []},
        "network": {"dns": [], "proxy": [], "certs": []},
        "finance": {"vendors": [], "transactions": [], "contracts": []}
    }
}


def _make_snapshot(run_id: str) -> dict:
    """Return MINIMAL_SNAPSHOT with run_id injected into meta"""
    import copy
    snap = copy.deepcopy(MINIMAL_SNAPSHOT)
    snap["meta"]["run_id"] = run_id
    return snap


class TestRunScopedIds:
    """Test that running same snapshot twice retains both runs' data"""

    @pytest.mark.asyncio
    async def test_both_runs_exist_after_rerun(self, pg_db_with_cleanup):
        """Both run_ids should exist in database after running same snapshot twice"""
        db, track = pg_db_with_cleanup
        run1_id = f"run_test_001_{uuid4().hex[:8]}"
        run2_id = f"run_test_002_{uuid4().hex[:8]}"
        track(run1_id)
        track(run2_id)
        started_at = datetime.utcnow()

        result1 = await execute_pipeline(
            _make_snapshot(run1_id), db,
            run_id=run1_id, started_at=started_at
        )
        assert result1.success, f"Run 1 failed: {result1.error}"

        result2 = await execute_pipeline(
            _make_snapshot(run2_id), db,
            run_id=run2_id, started_at=started_at
        )
        assert result2.success, f"Run 2 failed: {result2.error}"

        run1 = await db.get_run(run1_id)
        run2 = await db.get_run(run2_id)

        assert run1 is not None, "Run 1 should still exist after Run 2"
        assert run2 is not None, "Run 2 should exist"
        assert run1.aod_discovery_id != run2.aod_discovery_id, "Run IDs should be distinct"

    @pytest.mark.asyncio
    async def test_drill_sample_counts_match(self, pg_db_with_cleanup):
        """Drill sample counts should be identical for both runs"""
        db, track = pg_db_with_cleanup
        run1_id = f"run_drill_001_{uuid4().hex[:8]}"
        run2_id = f"run_drill_002_{uuid4().hex[:8]}"
        track(run1_id)
        track(run2_id)
        started_at = datetime.utcnow()

        result1 = await execute_pipeline(
            _make_snapshot(run1_id), db,
            run_id=run1_id, started_at=started_at
        )
        result2 = await execute_pipeline(
            _make_snapshot(run2_id), db,
            run_id=run2_id, started_at=started_at
        )

        assert result1.run_log.counts.observations_in == result2.run_log.counts.observations_in
        assert result1.run_log.counts.assets_admitted == result2.run_log.counts.assets_admitted
        assert result1.run_log.counts.findings_generated == result2.run_log.counts.findings_generated

    @pytest.mark.asyncio
    async def test_total_stored_rows_equals_sum(self, pg_db_with_cleanup):
        """Total stored rows should equal sum of both runs (no replacement)"""
        db, track = pg_db_with_cleanup
        run1_id = f"run_sum_001_{uuid4().hex[:8]}"
        run2_id = f"run_sum_002_{uuid4().hex[:8]}"
        track(run1_id)
        track(run2_id)
        started_at = datetime.utcnow()

        await execute_pipeline(
            _make_snapshot(run1_id), db,
            run_id=run1_id, started_at=started_at
        )

        assets1 = await db.get_assets_by_run(run1_id)
        count_after_run1 = len(assets1)

        await execute_pipeline(
            _make_snapshot(run2_id), db,
            run_id=run2_id, started_at=started_at
        )

        assets1_after = await db.get_assets_by_run(run1_id)
        assets2 = await db.get_assets_by_run(run2_id)

        assert len(assets1_after) == count_after_run1, "Run 1 assets should not be overwritten"
        assert len(assets2) == count_after_run1, "Run 2 should have same asset count"

    @pytest.mark.asyncio
    async def test_asset_ids_are_run_scoped(self, pg_db_with_cleanup):
        """Asset IDs should be different between runs (include run_id in hash)"""
        db, track = pg_db_with_cleanup
        run1_id = f"run_asset_001_{uuid4().hex[:8]}"
        run2_id = f"run_asset_002_{uuid4().hex[:8]}"
        track(run1_id)
        track(run2_id)
        started_at = datetime.utcnow()

        await execute_pipeline(
            _make_snapshot(run1_id), db,
            run_id=run1_id, started_at=started_at
        )
        await execute_pipeline(
            _make_snapshot(run2_id), db,
            run_id=run2_id, started_at=started_at
        )

        assets1 = await db.get_assets_by_run(run1_id)
        assets2 = await db.get_assets_by_run(run2_id)

        if assets1 and assets2:
            asset_ids_1 = {str(a.asset_id) for a in assets1}
            asset_ids_2 = {str(a.asset_id) for a in assets2}

            assert asset_ids_1.isdisjoint(asset_ids_2), \
                "Asset IDs should be unique per run (run-scoped)"
