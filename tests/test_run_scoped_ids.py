"""Regression test: run-scoped IDs prevent overwrites when re-running same snapshot"""

import pytest
import json
from datetime import datetime
from uuid import UUID

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
        "created_at": "2024-01-15T10:00:00Z"
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
                    "canonical_name": "Salesforce",
                    "display_name": "Salesforce CRM",
                    "object_type": "application"
                }
            ]
        },
        "cmdb": {"cis": []},
        "cloud": {"resources": []},
        "endpoint": {"devices": [], "installed_apps": []},
        "network": {"dns_records": [], "proxy_logs": [], "certificates": []},
        "finance": {"transactions": [], "contracts": []}
    }
}


@pytest.fixture
def fresh_db():
    """Create a database connection for testing"""
    import asyncio
    import os
    
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set - skipping integration test")
    
    db = Database(db_url)
    asyncio.get_event_loop().run_until_complete(db.initialize())
    return db


class TestRunScopedIds:
    """Test that running same snapshot twice retains both runs' data"""

    @pytest.mark.skip(reason="Requires full snapshot fixture - covered by nuke_check.py")
    @pytest.mark.asyncio
    async def test_both_runs_exist_after_rerun(self, fresh_db):
        """Both run_ids should exist in database after running same snapshot twice"""
        run1_id = "run_test_001"
        run2_id = "run_test_002"
        started_at = datetime.utcnow()
        
        result1 = await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run1_id, started_at=started_at
        )
        assert result1.success, f"Run 1 failed: {result1.error}"
        
        result2 = await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run2_id, started_at=started_at
        )
        assert result2.success, f"Run 2 failed: {result2.error}"
        
        run1 = await fresh_db.get_run(run1_id)
        run2 = await fresh_db.get_run(run2_id)
        
        assert run1 is not None, "Run 1 should still exist after Run 2"
        assert run2 is not None, "Run 2 should exist"
        assert run1.run_id != run2.run_id, "Run IDs should be distinct"

    @pytest.mark.skip(reason="Integration test - requires isolated database connection")
    @pytest.mark.asyncio
    async def test_drill_sample_counts_match(self, fresh_db):
        """Drill sample counts should be identical for both runs"""
        run1_id = "run_drill_001"
        run2_id = "run_drill_002"
        started_at = datetime.utcnow()
        
        result1 = await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run1_id, started_at=started_at
        )
        result2 = await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run2_id, started_at=started_at
        )
        
        assert result1.run_log.counts.observations_in == result2.run_log.counts.observations_in
        assert result1.run_log.counts.assets_admitted == result2.run_log.counts.assets_admitted
        assert result1.run_log.counts.findings_generated == result2.run_log.counts.findings_generated

    @pytest.mark.skip(reason="Integration test - requires isolated database connection")
    @pytest.mark.asyncio
    async def test_total_stored_rows_equals_sum(self, fresh_db):
        """Total stored rows should equal sum of both runs (no replacement)"""
        run1_id = "run_sum_001"
        run2_id = "run_sum_002"
        started_at = datetime.utcnow()
        
        await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run1_id, started_at=started_at
        )
        
        assets1 = await fresh_db.get_assets_by_run(run1_id)
        count_after_run1 = len(assets1)
        
        await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run2_id, started_at=started_at
        )
        
        assets1_after = await fresh_db.get_assets_by_run(run1_id)
        assets2 = await fresh_db.get_assets_by_run(run2_id)
        
        assert len(assets1_after) == count_after_run1, "Run 1 assets should not be overwritten"
        assert len(assets2) == count_after_run1, "Run 2 should have same asset count"
        
        all_runs = await fresh_db.get_all_runs()
        assert len(all_runs) == 2, "Both runs should exist"

    @pytest.mark.skip(reason="Integration test - requires isolated database connection")
    @pytest.mark.asyncio
    async def test_asset_ids_are_run_scoped(self, fresh_db):
        """Asset IDs should be different between runs (include run_id in hash)"""
        run1_id = "run_asset_001"
        run2_id = "run_asset_002"
        started_at = datetime.utcnow()
        
        await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run1_id, started_at=started_at
        )
        await execute_pipeline(
            MINIMAL_SNAPSHOT, fresh_db,
            run_id=run2_id, started_at=started_at
        )
        
        assets1 = await fresh_db.get_assets_by_run(run1_id)
        assets2 = await fresh_db.get_assets_by_run(run2_id)
        
        if assets1 and assets2:
            asset_ids_1 = {str(a.asset_id) for a in assets1}
            asset_ids_2 = {str(a.asset_id) for a in assets2}
            
            assert asset_ids_1.isdisjoint(asset_ids_2), \
                "Asset IDs should be unique per run (run-scoped)"
