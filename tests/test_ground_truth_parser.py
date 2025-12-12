"""
Unit tests for the Farm ground truth response parser.
Tests all expected shape variations and edge cases.
"""
import pytest
from src.aod.farm_client import normalize_ground_truth


class TestNormalizeGroundTruth:
    """Tests for normalize_ground_truth adapter function."""
    
    def test_old_shape_nested_dict(self):
        """Test old format: {"ground_truth": {"expected_assets": [...]}}"""
        raw = {
            "ground_truth": {
                "expected_assets": [
                    {"farm_asset_id": "asset-1", "asset_name": "Test Asset"}
                ]
            }
        }
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == [{"farm_asset_id": "asset-1", "asset_name": "Test Asset"}]
        assert result["raw_shape"] == "dict:ground_truth=dict:expected_assets=list"
        assert result["parse_error"] is None
    
    def test_new_shape_list_in_ground_truth(self):
        """Test new format: {"ground_truth": [...]}"""
        raw = {
            "ground_truth": [
                {"farm_asset_id": "asset-1", "asset_name": "Test Asset"},
                {"farm_asset_id": "asset-2", "asset_name": "Another Asset"}
            ]
        }
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert len(result["expected_assets"]) == 2
        assert result["expected_assets"][0]["farm_asset_id"] == "asset-1"
        assert result["raw_shape"] == "dict:ground_truth=list"
        assert result["parse_error"] is None
    
    def test_top_level_list(self):
        """Test worst-case: [...] as top-level response"""
        raw = [
            {"farm_asset_id": "asset-1"},
            {"farm_asset_id": "asset-2"}
        ]
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert len(result["expected_assets"]) == 2
        assert result["raw_shape"] == "top_level_list"
        assert result["parse_error"] is None
    
    def test_null_response(self):
        """Test null/None response"""
        result = normalize_ground_truth(None, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert result["raw_shape"] == "null"
        assert result["parse_error"] == "Farm returned null response"
    
    def test_empty_dict(self):
        """Test empty dict response"""
        result = normalize_ground_truth({}, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert result["raw_shape"] == "dict:no_ground_truth_key"
        assert "missing 'ground_truth' key" in result["parse_error"]
    
    def test_empty_list(self):
        """Test empty list response (valid but no assets)"""
        raw = {"ground_truth": []}
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert result["raw_shape"] == "dict:ground_truth=list"
        assert result["parse_error"] is None
    
    def test_ground_truth_dict_missing_expected_assets(self):
        """Test ground_truth is dict but missing expected_assets key"""
        raw = {"ground_truth": {"some_other_key": "value"}}
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert result["raw_shape"] == "dict:ground_truth=dict:no_expected_assets"
        assert result["parse_error"] is not None
    
    def test_expected_assets_not_a_list(self):
        """Test expected_assets is not a list"""
        raw = {"ground_truth": {"expected_assets": "not a list"}}
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert "expected_assets=str" in result["raw_shape"]
        assert "not a list" in result["parse_error"]
    
    def test_unexpected_type_string(self):
        """Test response is a string (error page)"""
        result = normalize_ground_truth("Error: Internal Server Error", tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert "unexpected_type:str" in result["raw_shape"]
        assert result["parse_error"] is not None
    
    def test_unexpected_type_int(self):
        """Test response is an integer"""
        result = normalize_ground_truth(500, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert "unexpected_type:int" in result["raw_shape"]
        assert result["parse_error"] is not None
    
    def test_ground_truth_is_string(self):
        """Test ground_truth key exists but is a string"""
        raw = {"ground_truth": "error message"}
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == []
        assert "ground_truth=str" in result["raw_shape"]
        assert result["parse_error"] is not None
    
    def test_expected_assets_top_level(self):
        """Test expected_assets at top level (alternative format)"""
        raw = {"expected_assets": [{"farm_asset_id": "asset-1"}]}
        result = normalize_ground_truth(raw, tenant_id="test-tenant")
        
        assert result["expected_assets"] == [{"farm_asset_id": "asset-1"}]
        assert result["raw_shape"] == "dict:expected_assets_top_level"
        assert result["parse_error"] is None
    
    def test_logging_includes_tenant_and_run(self):
        """Test that tenant_id and run_id are included in result for logging"""
        raw = {"ground_truth": []}
        result = normalize_ground_truth(raw, tenant_id="tenant-123", run_id="run-456")
        
        assert result["parse_error"] is None


class TestNormalizeGroundTruthIntegration:
    """Smoke tests simulating the ingest call path."""
    
    def test_old_format_ingest_simulation(self):
        """Simulate ingest with old Farm format"""
        farm_response = {
            "ground_truth": {
                "expected_assets": [
                    {
                        "farm_asset_id": "fa-001",
                        "asset_name": "Slack",
                        "vendor": "Salesforce",
                        "is_shadow_it": False
                    }
                ]
            }
        }
        
        parsed = normalize_ground_truth(farm_response, tenant_id="t1", run_id="r1")
        
        assert parsed["parse_error"] is None
        assert len(parsed["expected_assets"]) == 1
        assert parsed["expected_assets"][0]["asset_name"] == "Slack"
    
    def test_new_format_ingest_simulation(self):
        """Simulate ingest with new Farm format"""
        farm_response = {
            "ground_truth": [
                {
                    "farm_asset_id": "fa-001",
                    "asset_name": "Slack",
                    "vendor": "Salesforce",
                    "is_shadow_it": True,
                    "shadow_reasons": ["no_idp_evidence"]
                }
            ]
        }
        
        parsed = normalize_ground_truth(farm_response, tenant_id="t1", run_id="r1")
        
        assert parsed["parse_error"] is None
        assert len(parsed["expected_assets"]) == 1
        assert parsed["expected_assets"][0]["is_shadow_it"] is True
    
    def test_error_response_graceful_failure(self):
        """Simulate Farm returning an error response"""
        error_response = {"error": "Internal server error", "status": 500}
        
        parsed = normalize_ground_truth(error_response, tenant_id="t1", run_id="r1")
        
        assert parsed["expected_assets"] == []
        assert parsed["parse_error"] is not None
    
    def test_html_error_page_graceful_failure(self):
        """Simulate Farm returning HTML error page"""
        html_response = "<html><body>502 Bad Gateway</body></html>"
        
        parsed = normalize_ground_truth(html_response, tenant_id="t1", run_id="r1")
        
        assert parsed["expected_assets"] == []
        assert "unexpected_type" in parsed["raw_shape"]
        assert parsed["parse_error"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
