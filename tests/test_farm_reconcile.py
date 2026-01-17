"""Tests for Farm reconciliation module"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.aod.farm_reconcile import reconcile_to_farm
from src.aod.models.output_contracts import (
    RunLog, RunStatus, RunCounts, SyncStatus,
    Asset, AssetType, Environment, Finding, FindingType, FindingCategory, Severity,
    LensStatuses, LensCoverage, AssetIdentifiers, ActivityEvidence
)


@pytest.fixture
def sample_run_log():
    return RunLog(
        run_id="run_test123",
        tenant_id="tenant1",
        status=RunStatus.COMPLETED_WITH_RESULTS,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        counts=RunCounts(
            observations_in=100,
            candidates_out=50,
            assets_admitted=10,
            findings_generated=5
        )
    )


@pytest.fixture
def sample_assets():
    return [
        Asset(
            asset_id=uuid4(),
            tenant_id="tenant1",
            run_id="run_test123",
            name="Slack",
            asset_type=AssetType.SAAS,
            environment=Environment.PROD,
            identifiers=AssetIdentifiers(domains=["slack.com"]),
            lens_status=LensStatuses(),
            lens_coverage=LensCoverage(),
            activity_evidence=ActivityEvidence()
        )
    ]


@pytest.fixture
def sample_findings():
    return [
        Finding(
            finding_id=uuid4(),
            tenant_id="tenant1",
            run_id="run_test123",
            finding_type=FindingType.GOVERNANCE_GAP,
            category=FindingCategory.GOVERNANCE_FINDING,
            severity=Severity.CRITICAL,
            explanation="Asset lacks governance controls"
        )
    ]


@pytest.mark.asyncio
async def test_reconcile_no_farm_url(sample_run_log, sample_assets, sample_findings):
    """Test that reconcile fails gracefully without Farm URL"""
    with patch.dict('os.environ', {}, clear=True):
        success, error = await reconcile_to_farm(
            run_log=sample_run_log,
            assets=sample_assets,
            findings=sample_findings,
            snapshot_id="snap_123"
        )
        
        assert success is False
        assert error is not None and "No Farm URL" in error


@pytest.mark.asyncio
async def test_reconcile_success(sample_run_log, sample_assets, sample_findings):
    """Test successful reconciliation"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance
        
        success, error = await reconcile_to_farm(
            run_log=sample_run_log,
            assets=sample_assets,
            findings=sample_findings,
            snapshot_id="snap_123",
            farm_url="http://localhost:8000"
        )
        
        assert success is True
        assert error is None


@pytest.mark.asyncio
async def test_reconcile_http_error(sample_run_log, sample_assets, sample_findings):
    """Test handling of HTTP errors"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance
        
        success, error = await reconcile_to_farm(
            run_log=sample_run_log,
            assets=sample_assets,
            findings=sample_findings,
            snapshot_id="snap_123",
            farm_url="http://localhost:8000"
        )
        
        assert success is False
        assert error is not None and "500" in error


@pytest.mark.asyncio
async def test_reconcile_connection_error(sample_run_log, sample_assets, sample_findings):
    """Test handling of connection errors"""
    import httpx
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance
        
        success, error = await reconcile_to_farm(
            run_log=sample_run_log,
            assets=sample_assets,
            findings=sample_findings,
            snapshot_id="snap_123",
            farm_url="http://localhost:8000"
        )
        
        assert success is False
        assert error is not None and "Connection error" in error


@pytest.mark.asyncio
async def test_reconcile_timeout(sample_run_log, sample_assets, sample_findings):
    """Test handling of timeout errors"""
    import httpx
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance
        
        success, error = await reconcile_to_farm(
            run_log=sample_run_log,
            assets=sample_assets,
            findings=sample_findings,
            snapshot_id="snap_123",
            farm_url="http://localhost:8000"
        )
        
        assert success is False
        assert error is not None and "timed out" in error.lower()
