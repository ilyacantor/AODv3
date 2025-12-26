"""Tests for aggressive domain merging via base token matching."""

import pytest

from src.aod.models.input_contracts import Observation
from src.aod.pipeline.normalize_observations import (
    normalize_observations,
    extract_base_token,
)


class TestExtractBaseToken:
    """Tests for extract_base_token function."""
    
    def test_domain_extraction(self):
        assert extract_base_token("airtable.com", is_domain=True) == "airtable"
        assert extract_base_token("slack.com", is_domain=True) == "slack"
        assert extract_base_token("api.stripe.com", is_domain=True) == "stripe"
        assert extract_base_token("notion.so", is_domain=True) == "notion"
    
    def test_name_extraction(self):
        assert extract_base_token("Airtable", is_domain=False) == "airtable"
        assert extract_base_token("Slack", is_domain=False) == "slack"
        assert extract_base_token("Stripe", is_domain=False) == "stripe"
    
    def test_name_with_parentheses(self):
        assert extract_base_token("Airtable (Legacy)", is_domain=False) == "airtable"
        assert extract_base_token("Okta (Prod)", is_domain=False) == "okta"
    
    def test_name_with_env_suffixes(self):
        assert extract_base_token("Airtable-prod", is_domain=False) == "airtable"
        assert extract_base_token("Slack_staging", is_domain=False) == "slack"
        assert extract_base_token("PagerDuty-dev", is_domain=False) == "pagerduty"
    
    def test_empty_values(self):
        assert extract_base_token("", is_domain=True) is None
        assert extract_base_token("", is_domain=False) is None
        assert extract_base_token(None, is_domain=True) is None


class TestAggressiveDomainMerging:
    """Tests for aggressive domain merging in normalize_observations."""
    
    def test_airtable_name_plus_domain_creates_single_entity(self):
        """Airtable (name) + airtable.com (domain) → single entity with domain."""
        observations = [
            Observation(
                observation_id="obs_finance_1",
                name="Airtable",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="airtable.com",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "airtable.com"
        assert "obs_finance_1" in entity.observation_ids
        assert "obs_discovery_1" in entity.observation_ids
    
    def test_domain_first_then_name_merges(self):
        """Domain entity first, then name entity merges into it."""
        observations = [
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="slack.com",
                source="discovery"
            ),
            Observation(
                observation_id="obs_finance_1",
                name="Slack",
                domain=None,
                source="finance"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "slack.com"
        assert "obs_discovery_1" in entity.observation_ids
        assert "obs_finance_1" in entity.observation_ids
    
    def test_name_first_then_domain_upgrades(self):
        """Name entity created first gets upgraded when domain entity arrives."""
        observations = [
            Observation(
                observation_id="obs_finance_1",
                name="Notion",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="notion.so",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "notion.so"
        assert "obs_finance_1" in entity.observation_ids
        assert "obs_discovery_1" in entity.observation_ids
    
    def test_legacy_suffix_merges_with_domain(self):
        """Airtable (Legacy) should merge with airtable.com."""
        observations = [
            Observation(
                observation_id="obs_finance_1",
                name="Airtable (Legacy)",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="airtable.com",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "airtable.com"
        assert len(entity.observation_ids) == 2
    
    def test_env_suffix_merges_with_domain(self):
        """PagerDuty-prod should merge with pagerduty.com."""
        observations = [
            Observation(
                observation_id="obs_finance_1",
                name="PagerDuty-prod",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="pagerduty.com",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "pagerduty.com"
        assert "obs_finance_1" in entity.observation_ids
        assert "obs_discovery_1" in entity.observation_ids
    
    def test_different_base_tokens_stay_separate(self):
        """Different tools should remain as separate entities."""
        observations = [
            Observation(
                observation_id="obs_1",
                name="Airtable",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_2",
                name=None,
                domain="notion.so",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 2
        domains = [e.domain for e in entities]
        assert "notion.so" in domains
        assert "airtable.com" in domains
    
    def test_multiple_sources_all_merge(self):
        """Multiple observations from different sources all merge into one entity."""
        observations = [
            Observation(
                observation_id="obs_finance",
                name="Stripe",
                domain=None,
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery",
                name=None,
                domain="stripe.com",
                source="discovery"
            ),
            Observation(
                observation_id="obs_idp",
                name="Stripe",
                domain=None,
                source="idp"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "stripe.com"
        assert len(entity.observation_ids) == 3
        assert "obs_finance" in entity.observation_ids
        assert "obs_discovery" in entity.observation_ids
        assert "obs_idp" in entity.observation_ids
    
    def test_vendor_data_preserved_on_merge(self):
        """Vendor information from name-only entity transfers during merge."""
        observations = [
            Observation(
                observation_id="obs_finance_1",
                name="Datadog",
                domain=None,
                vendor="Datadog Inc",
                source="finance"
            ),
            Observation(
                observation_id="obs_discovery_1",
                name=None,
                domain="datadog.com",
                source="discovery"
            ),
        ]
        
        entities, rejected = normalize_observations(observations)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.domain == "datadog.com"
        assert entity.vendor == "datadog inc"
