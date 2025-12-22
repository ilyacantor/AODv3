"""
Performance and correctness tests for database query optimizations.

Tests verify:
1. Correctness: Batched queries return identical data to sequential queries
2. Performance: Batched queries are faster than sequential queries
3. Edge cases: Empty results, large datasets, filtering correctness

Run with: pytest tests/test_database_performance.py -v -s
"""

import pytest
import time
from typing import Optional
from datetime import datetime
from uuid import uuid4

# Note: These tests require a database connection
# Set DATABASE_URL or SUPABASE_DB_URL environment variable

pytestmark = pytest.mark.asyncio


class TestGetRunsByTenant:
    """Test get_runs_by_tenant() database filtering optimization."""

    async def test_filter_by_tenant_returns_correct_runs(self, db_with_test_data):
        """Verify tenant filtering returns only matching runs."""
        db, test_data = db_with_test_data

        # Get runs for tenant1
        tenant1_runs = await db.get_runs_by_tenant("tenant1")

        assert len(tenant1_runs) == 2, "Should return 2 runs for tenant1"
        assert all(r.tenant_id == "tenant1" for r in tenant1_runs), "All runs should belong to tenant1"

        # Verify run IDs match expected
        run_ids = {r.run_id for r in tenant1_runs}
        assert run_ids == {"run_1", "run_2"}

    async def test_filter_by_tenant_and_snapshot(self, db_with_test_data):
        """Verify filtering by both tenant and snapshot_id."""
        db, test_data = db_with_test_data

        # Get runs for tenant1 with snapshot_id = "snap_A"
        runs = await db.get_runs_by_tenant("tenant1", snapshot_id="snap_A")

        assert len(runs) == 1, "Should return 1 run matching both filters"
        assert runs[0].run_id == "run_1"
        assert runs[0].input_meta.get("snapshot_id") == "snap_A"

    async def test_filter_returns_empty_for_nonexistent_tenant(self, db_with_test_data):
        """Verify empty result for tenant with no runs."""
        db, test_data = db_with_test_data

        runs = await db.get_runs_by_tenant("nonexistent_tenant")

        assert len(runs) == 0, "Should return empty list for nonexistent tenant"

    async def test_filter_correctness_vs_get_all(self, db_with_test_data):
        """Verify get_runs_by_tenant() returns same data as filtering get_all_runs()."""
        db, test_data = db_with_test_data

        # Method 1: Database filtering
        db_filtered = await db.get_runs_by_tenant("tenant1")

        # Method 2: Application filtering (old way)
        all_runs = await db.get_all_runs()
        app_filtered = [r for r in all_runs if r.tenant_id == "tenant1"]

        # Should return same runs
        assert len(db_filtered) == len(app_filtered), "Both methods should return same count"

        db_run_ids = {r.run_id for r in db_filtered}
        app_run_ids = {r.run_id for r in app_filtered}
        assert db_run_ids == app_run_ids, "Both methods should return same run IDs"


class TestGetRunDataBatch:
    """Test get_run_data_batch() batched query optimization."""

    async def test_batch_returns_all_data(self, db_with_run_data):
        """Verify batched query returns assets, findings, and rejections."""
        db, run_id = db_with_run_data

        result = await db.get_run_data_batch(run_id)

        assert "assets" in result
        assert "findings" in result
        assert "rejections" in result
        assert len(result["assets"]) > 0, "Should have assets"
        assert len(result["findings"]) > 0, "Should have findings"

    async def test_batch_correctness_vs_sequential(self, db_with_run_data):
        """Verify batched query returns identical data to sequential queries."""
        db, run_id = db_with_run_data

        # Method 1: Batched query (new way)
        batch_result = await db.get_run_data_batch(run_id)

        # Method 2: Sequential queries (old way)
        seq_assets = await db.get_assets_by_run(run_id)
        seq_findings = await db.get_findings_by_run(run_id)
        seq_rejections, _ = await db.get_rejections_by_run(run_id, limit=100)

        # Compare assets
        assert len(batch_result["assets"]) == len(seq_assets), \
            "Batch and sequential should return same number of assets"

        batch_asset_ids = {str(a.asset_id) for a in batch_result["assets"]}
        seq_asset_ids = {str(a.asset_id) for a in seq_assets}
        assert batch_asset_ids == seq_asset_ids, "Asset IDs should match"

        # Compare findings
        assert len(batch_result["findings"]) == len(seq_findings), \
            "Batch and sequential should return same number of findings"

        batch_finding_ids = {str(f.finding_id) for f in batch_result["findings"]}
        seq_finding_ids = {str(f.finding_id) for f in seq_findings}
        assert batch_finding_ids == seq_finding_ids, "Finding IDs should match"

        # Compare rejections
        assert len(batch_result["rejections"]) == len(seq_rejections), \
            "Batch and sequential should return same number of rejections"

    async def test_batch_empty_run(self, db_with_empty_run):
        """Verify batched query handles run with no data."""
        db, run_id = db_with_empty_run

        result = await db.get_run_data_batch(run_id)

        assert result["assets"] == []
        assert result["findings"] == []
        assert result["rejections"] == []


class TestDatabasePerformance:
    """Benchmark database query performance improvements."""

    async def test_tenant_filter_performance(self, db_with_many_runs):
        """Benchmark get_runs_by_tenant() vs get_all_runs() + filter."""
        db, tenant_id = db_with_many_runs

        # Benchmark: Database filtering
        start = time.perf_counter()
        db_filtered = await db.get_runs_by_tenant(tenant_id)
        db_time = time.perf_counter() - start

        # Benchmark: Application filtering
        start = time.perf_counter()
        all_runs = await db.get_all_runs()
        app_filtered = [r for r in all_runs if r.tenant_id == tenant_id]
        app_time = time.perf_counter() - start

        print(f"\n📊 Tenant Filter Performance:")
        print(f"  Total runs in DB: {len(all_runs)}")
        print(f"  Filtered runs: {len(db_filtered)}")
        print(f"  Database filter time: {db_time * 1000:.2f} ms")
        print(f"  Application filter time: {app_time * 1000:.2f} ms")
        print(f"  Speedup: {app_time / db_time:.1f}x")

        # Database filtering should be faster (especially with many runs)
        assert db_time < app_time, "Database filtering should be faster than application filtering"
        assert len(db_filtered) == len(app_filtered), "Both methods should return same count"

    async def test_batch_query_performance(self, db_with_run_data):
        """Benchmark get_run_data_batch() vs sequential queries."""
        db, run_id = db_with_run_data

        # Benchmark: Batched query (new way)
        start = time.perf_counter()
        batch_result = await db.get_run_data_batch(run_id)
        batch_time = time.perf_counter() - start

        # Benchmark: Sequential queries (old way)
        start = time.perf_counter()
        seq_assets = await db.get_assets_by_run(run_id)
        seq_findings = await db.get_findings_by_run(run_id)
        seq_rejections, _ = await db.get_rejections_by_run(run_id, limit=100)
        seq_time = time.perf_counter() - start

        print(f"\n⚡ Batch Query Performance:")
        print(f"  Assets: {len(batch_result['assets'])}")
        print(f"  Findings: {len(batch_result['findings'])}")
        print(f"  Rejections: {len(batch_result['rejections'])}")
        print(f"  Batched query time: {batch_time * 1000:.2f} ms")
        print(f"  Sequential query time: {seq_time * 1000:.2f} ms")
        print(f"  Speedup: {seq_time / batch_time:.1f}x")

        # Batched query should be faster (fewer round-trips)
        # Note: Speedup depends on network latency and database load
        # Might not always be 3x faster in tests, but should be faster
        assert batch_time <= seq_time * 1.1, \
            "Batched query should be at least as fast as sequential (allowing 10% variance)"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def db_with_test_data():
    """
    Create database with test runs for different tenants.

    Creates:
    - 2 runs for tenant1 (with different snapshot_ids)
    - 1 run for tenant2
    """
    from aod.db.database import Database, get_database_url
    from aod.models.output_contracts import RunLog, RunStatus, RunCounts, SyncStatus

    db = Database(get_database_url())
    await db.initialize()

    # Create test runs
    runs = [
        RunLog(
            run_id="run_1",
            tenant_id="tenant1",
            status=RunStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            input_meta={"snapshot_id": "snap_A"},
            counts=RunCounts(),
            failure_reasons=[],
            sync_status=SyncStatus.NOT_APPLICABLE
        ),
        RunLog(
            run_id="run_2",
            tenant_id="tenant1",
            status=RunStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            input_meta={"snapshot_id": "snap_B"},
            counts=RunCounts(),
            failure_reasons=[],
            sync_status=SyncStatus.NOT_APPLICABLE
        ),
        RunLog(
            run_id="run_3",
            tenant_id="tenant2",
            status=RunStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            input_meta={"snapshot_id": "snap_C"},
            counts=RunCounts(),
            failure_reasons=[],
            sync_status=SyncStatus.NOT_APPLICABLE
        ),
    ]

    for run in runs:
        await db.create_run(run)

    yield db, {"runs": runs}

    # Cleanup
    await db.delete_all_runs()
    await db.close()


@pytest.fixture
async def db_with_run_data():
    """
    Create database with a run containing assets, findings, and rejections.
    """
    from aod.db.database import Database, get_database_url
    from aod.models.output_contracts import (
        RunLog, RunStatus, RunCounts, SyncStatus,
        Asset, AssetType, Environment, AssetIdentifiers,
        LensStatus, LensCoverage, ActivityEvidence,
        Finding, FindingType, FindingCategory, Severity,
        Confidence, Materiality, TriagePriority
    )

    db = Database(get_database_url())
    await db.initialize()

    run_id = f"test_run_{uuid4().hex[:8]}"

    # Create run
    run = RunLog(
        run_id=run_id,
        tenant_id="test_tenant",
        status=RunStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        input_meta={},
        counts=RunCounts(),
        failure_reasons=[],
        sync_status=SyncStatus.NOT_APPLICABLE
    )
    await db.create_run(run)

    # Create test assets
    for i in range(3):
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test_tenant",
            run_id=run_id,
            name=f"Test Asset {i}",
            asset_type=AssetType.APPLICATION,
            identifiers=AssetIdentifiers(),
            environment=Environment.PRODUCTION,
            evidence_refs=[],
            lens_status=LensStatus(),
            lens_coverage=LensCoverage(),
            activity_evidence=ActivityEvidence(),
            tags=[],
            admission_reason="test",
            created_at=datetime.now()
        )
        await db.create_asset(asset)

    # Create test findings
    for i in range(2):
        finding = Finding(
            finding_id=uuid4(),
            tenant_id="test_tenant",
            run_id=run_id,
            finding_type=FindingType.IDENTITY_GAP,
            category=FindingCategory.SECURITY_FINDING,
            severity=Severity.HIGH,
            explanation="Test finding",
            evidence_refs=[],
            created_at=datetime.now(),
            confidence=Confidence.HIGH,
            materiality=Materiality.HIGH,
            triage_priority=TriagePriority.P0
        )
        await db.create_finding(finding)

    yield db, run_id

    # Cleanup
    await db.delete_all_runs()
    await db.close()


@pytest.fixture
async def db_with_empty_run():
    """Create database with a run that has no assets/findings/rejections."""
    from aod.db.database import Database, get_database_url
    from aod.models.output_contracts import RunLog, RunStatus, RunCounts, SyncStatus

    db = Database(get_database_url())
    await db.initialize()

    run_id = f"empty_run_{uuid4().hex[:8]}"

    run = RunLog(
        run_id=run_id,
        tenant_id="test_tenant",
        status=RunStatus.COMPLETED_NO_ASSETS,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        input_meta={},
        counts=RunCounts(),
        failure_reasons=[],
        sync_status=SyncStatus.NOT_APPLICABLE
    )
    await db.create_run(run)

    yield db, run_id

    # Cleanup
    await db.delete_all_runs()
    await db.close()


@pytest.fixture
async def db_with_many_runs():
    """Create database with many runs to test filtering performance."""
    from aod.db.database import Database, get_database_url
    from aod.models.output_contracts import RunLog, RunStatus, RunCounts, SyncStatus

    db = Database(get_database_url())
    await db.initialize()

    target_tenant = "performance_test_tenant"

    # Create 50 runs (25 for target tenant, 25 for others)
    for i in range(50):
        tenant_id = target_tenant if i % 2 == 0 else f"other_tenant_{i // 2}"
        run = RunLog(
            run_id=f"perf_run_{i}",
            tenant_id=tenant_id,
            status=RunStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            input_meta={},
            counts=RunCounts(),
            failure_reasons=[],
            sync_status=SyncStatus.NOT_APPLICABLE
        )
        await db.create_run(run)

    yield db, target_tenant

    # Cleanup
    await db.delete_all_runs()
    await db.close()


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_database_performance.py -v -s
    pytest.main([__file__, "-v", "-s"])
