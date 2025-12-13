"""Integration tests for Farm HTTP pull integration"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, 'src')

from aod.farm_client import FarmClient, FarmFetchResult, validate_schema_version


class TestFarmClient:
    """Test FarmClient HTTP fetch and validation"""
    
    @pytest.mark.asyncio
    async def test_valid_snapshot_fetch(self):
        """Valid snapshot from Farm -> run completes successfully"""
        valid_snapshot = {
            "meta": {
                "tenant_id": "test-tenant",
                "run_id": "test-run-1",
                "schema_version": "farm.v1",
                "generated_at": datetime.utcnow().isoformat()
            },
            "planes": {
                "discovery": {"observations": [
                    {"observation_id": "obs-1", "name": "Salesforce", "source": "proxy"}
                ]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = json.dumps(valid_snapshot)
        mock_response.json.return_value = valid_snapshot
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            client = FarmClient("http://farm.example.com")
            result = await client.fetch_snapshot("snapshot-123")
            
            assert result.success is True
            assert result.data is not None
            assert result.data["meta"]["schema_version"] == "farm.v1"
    
    @pytest.mark.asyncio
    async def test_404_response_fails_with_explicit_error(self):
        """404 response -> run fails with explicit upstream error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            client = FarmClient("http://farm.example.com")
            result = await client.fetch_snapshot("nonexistent-snapshot")
            
            assert result.success is False
            assert result.error_type == "FARM_SNAPSHOT_NOT_FOUND"
            assert "not found" in result.error.lower()
            assert "404" in result.error
    
    @pytest.mark.asyncio
    async def test_html_response_fails_with_explicit_error(self):
        """HTML response -> run fails with explicit content-type error"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body>Error</body></html>"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            client = FarmClient("http://farm.example.com")
            result = await client.fetch_snapshot("snapshot-123")
            
            assert result.success is False
            assert result.error_type == "FARM_INVALID_CONTENT_TYPE"
            assert "text/html" in result.error
    
    @pytest.mark.asyncio
    async def test_empty_response_fails_with_explicit_error(self):
        """Empty response -> run fails with explicit error"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = ""
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            client = FarmClient("http://farm.example.com")
            result = await client.fetch_snapshot("snapshot-123")
            
            assert result.success is False
            assert result.error_type == "FARM_EMPTY_RESPONSE"
            assert "empty" in result.error.lower()


class TestSchemaVersionValidation:
    """Test schema_version validation"""
    
    def test_valid_farm_v1_schema(self):
        """Valid farm.v1 schema version passes"""
        data = {
            "meta": {
                "tenant_id": "t1",
                "run_id": "r1",
                "schema_version": "farm.v1"
            }
        }
        
        valid, error = validate_schema_version(data)
        assert valid is True
        assert error == ""
    
    def test_wrong_schema_version_fails(self):
        """Wrong schema_version -> fails with INVALID_INPUT_CONTRACT"""
        data = {
            "meta": {
                "tenant_id": "t1",
                "run_id": "r1",
                "schema_version": "farm.v2"
            }
        }
        
        valid, error = validate_schema_version(data)
        assert valid is False
        assert "farm.v2" in error
        assert "farm.v1" in error
    
    def test_missing_schema_version_fails(self):
        """Missing schema_version -> fails"""
        data = {
            "meta": {
                "tenant_id": "t1",
                "run_id": "r1"
            }
        }
        
        valid, error = validate_schema_version(data)
        assert valid is False
        assert "schema_version" in error.lower()
    
    def test_missing_meta_fails(self):
        """Missing meta -> fails"""
        data = {"planes": {}}
        
        valid, error = validate_schema_version(data)
        assert valid is False
        assert "meta" in error.lower()


class TestFarmClientHTTPErrors:
    """Test FarmClient handles various HTTP errors"""
    
    @pytest.mark.asyncio
    async def test_500_server_error(self):
        """500 server error -> fails with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            client = FarmClient("http://farm.example.com")
            result = await client.fetch_snapshot("snapshot-123")
            
            assert result.success is False
            assert result.error_type == "FARM_HTTP_ERROR"
            assert "500" in result.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
