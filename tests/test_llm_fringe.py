"""Tests for LLM fringe resolution with stubbed clients"""

import pytest
import sys
sys.path.insert(0, 'src')

from uuid import UUID
from datetime import datetime, timezone

from aod.llm.client import LLMClient, LLMResponse
from aod.llm.fringe_resolver import (
    resolve_fringe, FringeInput, FringeResolution,
    build_fringe_prompt, CONFIDENCE_THRESHOLD, FRINGE_SCHEMA
)
from aod.models.output_contracts import (
    Asset, AssetType, AssetIdentifiers, LensStatuses, LensCoverage,
    ActivityEvidence, LensStatus, LLMMetadata
)
from aod.pipeline.derived_classifications import classify_shadow, classify_zombie


class StubLLMClient(LLMClient):
    """Stubbed LLM client for testing"""
    
    def __init__(self, response_data: dict = None, should_fail: bool = False, error_msg: str = ""):
        self._response_data = response_data or {}
        self._should_fail = should_fail
        self._error_msg = error_msg
        self._calls = []
    
    @property
    def provider(self) -> str:
        return "stub"
    
    @property
    def model_id(self) -> str:
        return "stub-model-v1"
    
    async def generate_json(self, prompt: str, schema: dict) -> LLMResponse:
        self._calls.append({"prompt": prompt, "schema": schema})
        
        if self._should_fail:
            return LLMResponse(
                success=False,
                error=self._error_msg or "Stub error",
                provider=self.provider,
                model_id=self.model_id
            )
        
        return LLMResponse(
            success=True,
            data=self._response_data,
            provider=self.provider,
            model_id=self.model_id
        )


class TestFringePromptBuilding:
    """Test prompt building for fringe resolution"""
    
    def test_builds_prompt_with_domain(self):
        fringe_input = FringeInput(
            entity_key="slack.com",
            domain="slack.com",
            canonical_name="Slack",
            observed_names=["slack", "Slack", "slack.com"],
            vendor_hint="Salesforce",
            sources={"discovery", "network"},
            recent_activity=True,
        )
        
        prompt = build_fringe_prompt(fringe_input)
        
        assert "Entity Key: slack.com" in prompt
        assert "Domain: slack.com" in prompt
        assert "Canonical Name: Slack" in prompt
        assert "Vendor Hint: Salesforce" in prompt
        assert "Recent Activity: True" in prompt
        assert "SAAS_APP" in prompt
        assert "INFRA_TECH" in prompt
    
    def test_builds_prompt_with_cmdb_candidates(self):
        fringe_input = FringeInput(
            entity_key="redis.io",
            domain="redis.io",
            canonical_name="Redis",
            cmdb_candidates=[
                {"ci_id": "ci-001", "name": "Redis Cache", "ci_type": "database", "lifecycle": "production", "vendor": "Redis Labs"},
                {"ci_id": "ci-002", "name": "Redis Enterprise", "ci_type": "database", "lifecycle": "production", "vendor": "Redis Labs"},
            ]
        )
        
        prompt = build_fringe_prompt(fringe_input)
        
        assert "CMDB Candidates (top 10):" in prompt
        assert "CI ID: ci-001" in prompt
        assert "Redis Cache" in prompt
        assert "ci-002" in prompt
    
    def test_builds_prompt_with_idp_candidates(self):
        fringe_input = FringeInput(
            entity_key="okta.com",
            domain="okta.com",
            canonical_name="Okta",
            idp_candidates=[
                {"id": "idp-001", "name": "Okta Admin", "vendor": "Okta", "has_sso": True, "has_scim": True},
            ]
        )
        
        prompt = build_fringe_prompt(fringe_input)
        
        assert "IdP Candidates (top 10):" in prompt
        assert "ID: idp-001" in prompt
        assert "Okta Admin" in prompt
        assert "SSO: True" in prompt


class TestFringeResolution:
    """Test fringe resolution with stubbed LLM"""
    
    @pytest.mark.asyncio
    async def test_resolves_saas_with_high_confidence(self):
        client = StubLLMClient(response_data={
            "asset_type": "SAAS_APP",
            "entity_role": "VENDOR",
            "canonical_vendor": "Salesforce",
            "canonical_product": "Slack",
            "cmdb_ci_id": None,
            "idp_object_id": None,
            "confidence": 0.95,
            "reason": "Well-known SaaS messaging platform by Salesforce"
        })
        
        fringe_input = FringeInput(
            entity_key="slack.com",
            domain="slack.com",
            canonical_name="Slack",
        )
        
        result = await resolve_fringe(fringe_input, gemini_client=client)
        
        assert result.resolved is True
        assert result.asset_type == "SAAS_APP"
        assert result.canonical_vendor == "Salesforce"
        assert result.confidence == 0.95
        assert result.llm_provider == "stub"
    
    @pytest.mark.asyncio
    async def test_identifies_infra_tech(self):
        client = StubLLMClient(response_data={
            "asset_type": "INFRA_TECH",
            "entity_role": "PRODUCT",
            "canonical_vendor": "Redis Labs",
            "canonical_product": "Redis",
            "cmdb_ci_id": None,
            "idp_object_id": None,
            "confidence": 0.92,
            "reason": "Redis is an in-memory database, infrastructure technology"
        })
        
        fringe_input = FringeInput(
            entity_key="redis.io",
            domain="redis.io",
            canonical_name="Redis",
        )
        
        result = await resolve_fringe(fringe_input, gemini_client=client)
        
        assert result.resolved is True
        assert result.asset_type == "INFRA_TECH"
        assert result.confidence >= CONFIDENCE_THRESHOLD
    
    @pytest.mark.asyncio
    async def test_rejects_low_confidence(self):
        client = StubLLMClient(response_data={
            "asset_type": "UNKNOWN",
            "entity_role": "UNKNOWN",
            "canonical_vendor": None,
            "canonical_product": None,
            "cmdb_ci_id": None,
            "idp_object_id": None,
            "confidence": 0.45,
            "reason": "Cannot determine asset type with confidence"
        })
        
        fringe_input = FringeInput(
            entity_key="internal-app.local",
            canonical_name="internal-app",
        )
        
        result = await resolve_fringe(fringe_input, gemini_client=client)
        
        assert result.resolved is False
        assert result.confidence < CONFIDENCE_THRESHOLD
        assert "LLM_INCONCLUSIVE" in result.reason
    
    @pytest.mark.asyncio
    async def test_matches_cmdb_ci(self):
        client = StubLLMClient(response_data={
            "asset_type": "SAAS_APP",
            "entity_role": "PRODUCT",
            "canonical_vendor": "PagerDuty",
            "canonical_product": "PagerDuty",
            "cmdb_ci_id": "cmdb-pagerduty-001",
            "idp_object_id": None,
            "confidence": 0.88,
            "reason": "Matched to CMDB CI for PagerDuty incident management"
        })
        
        fringe_input = FringeInput(
            entity_key="pagerduty.com",
            domain="pagerduty.com",
            canonical_name="PagerDuty",
            cmdb_candidates=[
                {"ci_id": "cmdb-pagerduty-001", "name": "PagerDuty", "ci_type": "saas", "lifecycle": "production", "vendor": "PagerDuty"},
            ]
        )
        
        result = await resolve_fringe(fringe_input, gemini_client=client)
        
        assert result.resolved is True
        assert result.cmdb_ci_id == "cmdb-pagerduty-001"
    
    @pytest.mark.asyncio
    async def test_fallback_to_openai_on_gemini_failure(self):
        gemini_client = StubLLMClient(should_fail=True, error_msg="Gemini API rate limited")
        openai_client = StubLLMClient(response_data={
            "asset_type": "SAAS_APP",
            "entity_role": "VENDOR",
            "canonical_vendor": "Zoom",
            "canonical_product": "Zoom Meetings",
            "cmdb_ci_id": None,
            "idp_object_id": None,
            "confidence": 0.90,
            "reason": "Zoom video conferencing SaaS"
        })
        
        fringe_input = FringeInput(
            entity_key="zoom.us",
            domain="zoom.us",
            canonical_name="Zoom",
        )
        
        result = await resolve_fringe(fringe_input, gemini_client=gemini_client, openai_client=openai_client)
        
        assert result.resolved is True
        assert result.asset_type == "SAAS_APP"
        assert len(gemini_client._calls) == 1
        assert len(openai_client._calls) == 1
    
    @pytest.mark.asyncio
    async def test_returns_error_when_no_clients(self):
        fringe_input = FringeInput(
            entity_key="test.com",
            canonical_name="Test",
        )
        
        result = await resolve_fringe(fringe_input)
        
        assert result.resolved is False
        assert "No LLM clients available" in (result.error or "")


class TestInfraTechExclusion:
    """Test that INFRA_TECH assets are excluded from shadow/zombie classification"""
    
    def _make_asset(
        self,
        name: str = "Redis",
        has_discovery: bool = True,
        has_idp: bool = False,
        has_cmdb: bool = False,
        has_activity: bool = True,
        llm_exclusion_reason: str = None,
        llm_confidence: float = 0.0,
    ) -> Asset:
        """Helper to create test assets"""
        llm_meta = None
        if llm_exclusion_reason:
            llm_meta = LLMMetadata(
                llm_used=True,
                llm_confidence=llm_confidence,
                llm_reason="LLM identified as infrastructure technology",
                llm_asset_type="INFRA_TECH",
                exclusion_reason=llm_exclusion_reason,
            )
        
        return Asset(
            asset_id=UUID("00000000-0000-0000-0000-000000000001"),
            tenant_id="t1",
            run_id="r1",
            name=name,
            asset_type=AssetType.INFRA,
            identifiers=AssetIdentifiers(domains=["redis.io"]),
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED if has_idp else LensStatus.UNMATCHED,
                cmdb=LensStatus.MATCHED if has_cmdb else LensStatus.UNMATCHED,
            ),
            lens_coverage=LensCoverage(
                discovery=has_discovery,
            ),
            activity_evidence=ActivityEvidence(
                latest_activity_at=datetime.now(timezone.utc) if has_activity else None,
            ),
            llm_metadata=llm_meta,
        )
    
    def test_infra_tech_excluded_from_shadow(self):
        """INFRA_TECH assets should not be classified as shadow"""
        asset = self._make_asset(
            name="Redis",
            has_discovery=True,
            has_idp=False,
            has_cmdb=False,
            has_activity=True,
            llm_exclusion_reason="asset_type_infra_tech",
            llm_confidence=0.92,
        )
        
        result = classify_shadow(asset)
        
        assert result.is_classified is False
        assert "INFRA_TECH" in result.reason
        assert "excluded" in result.reason.lower()
    
    def test_infra_tech_excluded_from_zombie(self):
        """INFRA_TECH assets should not be classified as zombie"""
        asset = self._make_asset(
            name="PostgreSQL",
            has_discovery=False,
            has_idp=True,
            has_cmdb=True,
            has_activity=False,
            llm_exclusion_reason="asset_type_infra_tech",
            llm_confidence=0.88,
        )
        
        result = classify_zombie(asset)
        
        assert result.is_classified is False
        assert "INFRA_TECH" in result.reason
    
    def test_non_infra_tech_still_classified_as_shadow(self):
        """Non-INFRA_TECH assets without governance should still be shadow"""
        asset = self._make_asset(
            name="Slack",
            has_discovery=True,
            has_idp=False,
            has_cmdb=False,
            has_activity=True,
            llm_exclusion_reason=None,
        )
        
        result = classify_shadow(asset)
        
        assert result.is_classified is True
        assert "shadow" in result.reason.lower()
    
    def test_non_infra_tech_still_classified_as_zombie(self):
        """Non-INFRA_TECH assets with stale governance should still be zombie"""
        asset = self._make_asset(
            name="OldApp",
            has_discovery=False,
            has_idp=True,
            has_cmdb=False,
            has_activity=False,
            llm_exclusion_reason=None,
        )
        
        result = classify_zombie(asset)
        
        assert result.is_classified is True
        assert "zombie" in result.reason.lower()


class TestLLMMetadataOnAsset:
    """Test LLMMetadata model on Asset"""
    
    def test_asset_with_llm_metadata(self):
        metadata = LLMMetadata(
            llm_used=True,
            llm_confidence=0.91,
            llm_reason="High confidence SaaS identification",
            llm_asset_type="SAAS_APP",
            llm_canonical_vendor="Salesforce",
            llm_provider="gemini",
            llm_model_id="gemini-2.5-flash",
            fact_id="fact-12345",
            exclusion_reason=None,
            cmdb_match_method="llm_adjudicated",
        )
        
        asset = Asset(
            asset_id=UUID("00000000-0000-0000-0000-000000000002"),
            tenant_id="t1",
            run_id="r1",
            name="Slack",
            llm_metadata=metadata,
        )
        
        assert asset.llm_metadata is not None
        assert asset.llm_metadata.llm_used is True
        assert asset.llm_metadata.llm_confidence == 0.91
        assert asset.llm_metadata.cmdb_match_method == "llm_adjudicated"
    
    def test_asset_without_llm_metadata(self):
        asset = Asset(
            asset_id=UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id="t1",
            run_id="r1",
            name="Known App",
        )
        
        assert asset.llm_metadata is None
    
    def test_llm_metadata_serialization(self):
        metadata = LLMMetadata(
            llm_used=True,
            llm_confidence=0.85,
            llm_reason="Test reason",
        )
        
        asset = Asset(
            asset_id=UUID("00000000-0000-0000-0000-000000000004"),
            tenant_id="t1",
            run_id="r1",
            name="Test",
            llm_metadata=metadata,
        )
        
        data = asset.model_dump()
        
        assert data["llm_metadata"]["llm_used"] is True
        assert data["llm_metadata"]["llm_confidence"] == 0.85
        assert data["llm_metadata"]["llm_reason"] == "Test reason"
