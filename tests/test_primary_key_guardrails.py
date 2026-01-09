"""
Guardrail tests for primary key selection and immutability.

These tests ensure that the KEY_NORMALIZATION_MISMATCH fix maintains:
1. Key determinism - same observations produce same key
2. Key immutability - entity.domain never changes once set
3. No regressions in known mismatch cases
"""

import pytest
from datetime import datetime, timezone

from src.aod.models.input_contracts import Observation
from src.aod.pipeline.normalize_observations import (
    normalize_observations,
    choose_primary_key_from_observations,
    resolve_domain_from_observation,
)


class TestKeyDeterminism:
    """Ensure key selection is deterministic regardless of observation order."""
    
    def test_same_observations_produce_same_key(self):
        """Same observations should produce identical entity.domain."""
        obs1 = Observation(
            observation_id="obs-1",
            name="Amazon Web Services",
            domain="aws.amazon.com",
            source="proxy",
            timestamp=datetime(2025, 11, 1, tzinfo=timezone.utc)
        )
        obs2 = Observation(
            observation_id="obs-2",
            name="Amazon",
            domain="amazon.com",
            source="dns",
            timestamp=datetime(2025, 11, 2, tzinfo=timezone.utc)
        )
        
        entities_a, _ = normalize_observations([obs1, obs2])
        entities_b, _ = normalize_observations([obs1, obs2])
        
        assert len(entities_a) == 1
        assert len(entities_b) == 1
        assert entities_a[0].domain == entities_b[0].domain
    
    def test_order_independent_key_selection(self):
        """Key selection should not depend on observation processing order."""
        obs1 = Observation(
            observation_id="obs-1",
            name="Amazon Web Services",
            domain="aws.amazon.com",
            source="proxy",
            timestamp=datetime(2025, 11, 1, tzinfo=timezone.utc)
        )
        obs2 = Observation(
            observation_id="obs-2",
            name="Amazon",
            domain="amazon.com",
            source="dns",
            timestamp=datetime(2025, 11, 2, tzinfo=timezone.utc)
        )
        obs3 = Observation(
            observation_id="obs-3",
            name="Amazon Cloud",
            domain="amazon.com",
            source="casb",
            timestamp=datetime(2025, 11, 3, tzinfo=timezone.utc)
        )
        
        entities_order_a, _ = normalize_observations([obs1, obs2, obs3])
        entities_order_b, _ = normalize_observations([obs3, obs1, obs2])
        entities_order_c, _ = normalize_observations([obs2, obs3, obs1])
        
        assert len(entities_order_a) == len(entities_order_b) == len(entities_order_c)
        assert entities_order_a[0].domain == entities_order_b[0].domain == entities_order_c[0].domain
    
    def test_higher_support_count_wins(self):
        """Domain with more observations should win."""
        obs1 = Observation(observation_id="obs-1", name="Slack", domain="slack.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Slack", domain="slack.com", source="dns")
        obs3 = Observation(observation_id="obs-3", name="Slack", domain="api.slack.com", source="casb")
        
        primary_key = choose_primary_key_from_observations([obs1, obs2, obs3])
        
        assert primary_key == "slack.com"
    
    def test_higher_source_diversity_wins(self):
        """Domain with more diverse sources should win when counts are equal."""
        obs1 = Observation(observation_id="obs-1", name="Slack", domain="slack.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Slack", domain="slack.com", source="proxy")
        obs3 = Observation(observation_id="obs-3", name="Slack", domain="api.slack.com", source="dns")
        obs4 = Observation(observation_id="obs-4", name="Slack", domain="api.slack.com", source="casb")
        
        primary_key = choose_primary_key_from_observations([obs1, obs2, obs3, obs4])
        
        assert primary_key == "slack.com"


class TestKeyImmutability:
    """Ensure entity.domain never changes once set."""
    
    def test_entity_domain_set_once(self):
        """Entity domain should be consistent across multiple calls."""
        obs1 = Observation(observation_id="obs-1", name="Salesforce", domain="salesforce.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Salesforce", domain="api.salesforce.com", source="dns")
        
        entities, _ = normalize_observations([obs1, obs2])
        
        assert len(entities) == 1
        original_domain = entities[0].domain
        
        entities_again, _ = normalize_observations([obs1, obs2])
        
        assert entities_again[0].domain == original_domain
        assert original_domain == "salesforce.com"
    
    def test_entity_id_matches_domain(self):
        """Entity ID should be based on the chosen domain."""
        obs1 = Observation(observation_id="obs-1", name="GitHub", domain="github.com", source="proxy")
        
        entities, _ = normalize_observations([obs1])
        
        assert len(entities) == 1
        assert entities[0].domain == "github.com"
        assert entities[0].entity_id == "entity:github.com"
        assert entities[0].canonical_name == "github.com"


class TestChoosePrimaryKeyFromObservations:
    """Unit tests for the primary key selection function."""
    
    def test_empty_observations_returns_none(self):
        """Empty observation list should return None."""
        assert choose_primary_key_from_observations([]) is None
    
    def test_single_observation_with_domain(self):
        """Single observation should return its domain."""
        obs = Observation(observation_id="obs-1", name="Notion", domain="notion.so", source="proxy")
        
        assert choose_primary_key_from_observations([obs]) == "notion.so"
    
    def test_single_observation_without_domain(self):
        """Single observation without domain should return None."""
        obs = Observation(observation_id="obs-1", name="Unknown App", domain=None, source="proxy")
        
        assert choose_primary_key_from_observations([obs]) is None
    
    def test_subdomain_normalizes_to_registered(self):
        """Subdomains should normalize to registered domain for comparison."""
        obs1 = Observation(observation_id="obs-1", name="Jira", domain="jira.atlassian.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Jira", domain="confluence.atlassian.com", source="dns")
        
        primary_key = choose_primary_key_from_observations([obs1, obs2])
        
        assert primary_key == "atlassian.com"


class TestKnownMismatchCases:
    """Regression tests for previously known KEY_NORMALIZATION_MISMATCH cases."""
    
    def test_amazon_aws_normalization(self):
        """Amazon and AWS domains should normalize to amazon.com."""
        obs_amazon = Observation(observation_id="obs-1", name="Amazon", domain="amazon.com", source="proxy")
        obs_aws = Observation(observation_id="obs-2", name="AWS", domain="aws.amazon.com", source="dns")
        
        entities, _ = normalize_observations([obs_amazon, obs_aws])
        
        assert len(entities) == 1
        assert entities[0].domain == "amazon.com"
    
    def test_microsoft_domains_normalization(self):
        """Microsoft-related domains should normalize consistently."""
        obs1 = Observation(observation_id="obs-1", name="Microsoft 365", domain="microsoft.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Azure", domain="azure.microsoft.com", source="dns")
        
        entities, _ = normalize_observations([obs1, obs2])
        
        assert len(entities) == 1
        assert entities[0].domain == "microsoft.com"
    
    def test_google_domains_normalization(self):
        """Google-related domains should normalize consistently."""
        obs1 = Observation(observation_id="obs-1", name="Google", domain="google.com", source="proxy")
        obs2 = Observation(observation_id="obs-2", name="Google", domain="mail.google.com", source="dns")
        obs3 = Observation(observation_id="obs-3", name="Google", domain="docs.google.com", source="casb")
        
        entities, _ = normalize_observations([obs1, obs2, obs3])
        
        assert len(entities) == 1
        assert entities[0].domain == "google.com"
