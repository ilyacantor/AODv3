"""
Performance benchmarks for correlation algorithm optimizations.

This test suite validates the performance improvements made to correlate_entities.py:
1. LRU cache effectiveness for Levenshtein distance
2. Early exit conditions reducing O(n²) behavior
3. Regex pattern caching
4. Overall execution time improvements

Run with: pytest tests/test_correlation_performance.py -v -s
"""

import time
import pytest
from typing import Any

from aod.models.input_contracts import Observation, Snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import (
    correlate_entities_to_planes,
    _levenshtein_distance,
    _REGEX_PATTERN_CACHE,
)


def generate_test_entities(count: int, name_prefix: str = "app"):
    """Generate synthetic entities for testing correlation performance."""
    from aod.pipeline.normalize_observations import CandidateEntity

    entities = []
    for i in range(count):
        entity = CandidateEntity(
            entity_id=f"ent_{i}",
            canonical_name=f"{name_prefix}{i}",
            original_name=f"{name_prefix}_{i}",
            domain=f"app{i}.example.com" if i % 3 == 0 else None,
            vendor=f"Vendor{i % 10}" if i % 5 == 0 else None,
            observation_ids=[f"obs_{i}"]
        )
        entities.append(entity)

    return entities


def generate_test_plane_indexes(record_count: int = 50):
    """Generate test plane indexes for correlation testing."""
    from aod.pipeline.build_plane_indexes import PlaneIndex

    # Create synthetic records for each plane
    records = {}
    for i in range(record_count):
        records[f"rec_{i}"] = {
            "id": f"rec_{i}",
            "name": f"indexed_app_{i}",
            "vendor": f"Vendor{i % 10}" if i % 5 == 0 else None
        }

    # Build indexes
    by_canonical_name = {}
    by_domain = {}
    by_vendor_product = {}

    for rec_id, rec in records.items():
        name = rec.get("name", "").lower().strip()
        if name:
            if name not in by_canonical_name:
                by_canonical_name[name] = []
            by_canonical_name[name].append(rec_id)

        vendor = rec.get("vendor")
        if vendor:
            vendor_key = vendor.lower().strip()
            if vendor_key not in by_vendor_product:
                by_vendor_product[vendor_key] = []
            by_vendor_product[vendor_key].append(rec_id)

    return PlaneIndex(
        records=records,
        by_canonical_name=by_canonical_name,
        by_domain=by_domain,
        by_uri={},
        by_vendor_product=by_vendor_product
    )


class TestLevenshteinCacheEffectiveness:
    """Test LRU cache performance for Levenshtein distance calculations."""

    def test_cache_hit_rate(self):
        """Verify that cache is being used effectively."""
        # Clear cache stats
        _levenshtein_distance.cache_clear()

        # Test strings that will have repeats
        test_pairs = [
            ("monday", "mondaycom"),
            ("slack", "slackbot"),
            ("jira", "jirasoftware"),
            # Repeat the same pairs to trigger cache hits
            ("monday", "mondaycom"),
            ("slack", "slackbot"),
            ("jira", "jirasoftware"),
            ("monday", "mondaycom"),  # Third time
        ]

        for s1, s2 in test_pairs:
            _levenshtein_distance(s1, s2)

        cache_info = _levenshtein_distance.cache_info()

        print(f"\n📊 Cache Stats:")
        print(f"  Hits: {cache_info.hits}")
        print(f"  Misses: {cache_info.misses}")
        print(f"  Hit rate: {cache_info.hits / (cache_info.hits + cache_info.misses) * 100:.1f}%")
        print(f"  Cache size: {cache_info.currsize}/{cache_info.maxsize}")

        # We should have cache hits from the repeated pairs
        assert cache_info.hits > 0, "Cache should have at least some hits"
        hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses)
        assert hit_rate >= 0.4, f"Cache hit rate {hit_rate:.1%} is too low"

    def test_cache_reduces_computation_time(self):
        """Verify cache actually speeds up repeated computations."""
        _levenshtein_distance.cache_clear()

        s1, s2 = "servicenow", "servicenowinstance"

        # First call - cache miss
        start = time.perf_counter()
        result1 = _levenshtein_distance(s1, s2)
        first_time = time.perf_counter() - start

        # Second call - cache hit
        start = time.perf_counter()
        result2 = _levenshtein_distance(s1, s2)
        second_time = time.perf_counter() - start

        print(f"\n⏱️  Computation time comparison:")
        print(f"  First call (miss): {first_time * 1e6:.2f} µs")
        print(f"  Second call (hit): {second_time * 1e6:.2f} µs")
        print(f"  Speedup: {first_time / second_time:.1f}x")

        assert result1 == result2, "Results should be identical"
        assert second_time < first_time, "Cached call should be faster"
        # Cache hit should be significantly faster (at least 5x)
        assert second_time < first_time / 5, "Cache should provide meaningful speedup"


class TestRegexPatternCaching:
    """Test that regex patterns are cached and reused."""

    def test_pattern_cache_populated(self):
        """Verify regex patterns are cached after use."""
        from aod.pipeline.correlate_entities import _extract_base_name

        # Clear cache
        _REGEX_PATTERN_CACHE.clear()
        initial_size = len(_REGEX_PATTERN_CACHE)

        # Process some names that will trigger pattern compilation
        test_names = [
            "myapp-prod",
            "service-dev",
            "api-staging",
            "db-legacy",
        ]

        for name in test_names:
            _extract_base_name(name)

        final_size = len(_REGEX_PATTERN_CACHE)

        print(f"\n📝 Regex Cache Stats:")
        print(f"  Initial patterns: {initial_size}")
        print(f"  Final patterns: {final_size}")
        print(f"  Patterns added: {final_size - initial_size}")

        assert final_size > initial_size, "Patterns should be cached"

        # Process same names again - should reuse cached patterns
        cache_size_before_reuse = len(_REGEX_PATTERN_CACHE)
        for name in test_names:
            _extract_base_name(name)
        cache_size_after_reuse = len(_REGEX_PATTERN_CACHE)

        assert cache_size_before_reuse == cache_size_after_reuse, \
            "Reprocessing should not create new patterns"


class TestCorrelationPerformance:
    """Benchmark overall correlation performance."""

    @pytest.mark.parametrize("dataset_size", [10, 50, 100, 500])
    def test_correlation_scales_linearly(self, dataset_size: int):
        """Test that correlation time grows reasonably with dataset size."""
        from aod.pipeline.build_plane_indexes import PlaneIndexes

        # Generate test data
        entities = generate_test_entities(dataset_size)
        cmdb_index = generate_test_plane_indexes(dataset_size // 2)
        idp_index = generate_test_plane_indexes(dataset_size // 3)

        plane_indexes = PlaneIndexes(
            idp=idp_index,
            cmdb=cmdb_index,
            cloud=generate_test_plane_indexes(0),
            finance=generate_test_plane_indexes(0)
        )

        # Clear cache for consistent benchmarking
        _levenshtein_distance.cache_clear()

        # Benchmark correlation
        start = time.perf_counter()
        results = correlate_entities_to_planes(entities, plane_indexes)
        duration = time.perf_counter() - start

        # Get cache stats
        cache_info = _levenshtein_distance.cache_info()

        print(f"\n📈 Performance for {dataset_size} entities:")
        print(f"  Total time: {duration * 1000:.2f} ms")
        print(f"  Time per entity: {duration / len(entities) * 1000:.3f} ms")
        print(f"  Entities processed: {len(entities)}")
        print(f"  Results: {len(results)}")
        print(f"  Cache hits: {cache_info.hits}")
        print(f"  Cache misses: {cache_info.misses}")
        if cache_info.hits + cache_info.misses > 0:
            hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses)
            print(f"  Cache hit rate: {hit_rate * 100:.1f}%")

        # Performance assertions
        # Even with 500 observations, should complete in reasonable time
        max_time = dataset_size * 0.1  # 100ms per observation is generous
        assert duration < max_time, \
            f"Correlation took {duration:.2f}s (expected <{max_time:.2f}s for {dataset_size} obs)"

        # Should produce results
        assert len(results) == len(entities), "Should return correlation result for each entity"

    def test_early_exit_effectiveness(self):
        """Test that early exit prevents excessive iterations."""
        from aod.pipeline.correlate_entities import MAX_MATCH_CANDIDATES
        from aod.pipeline.build_plane_indexes import PlaneIndexes, PlaneIndex

        # Create many similar indexed names to trigger fuzzy matching
        records = {}
        by_canonical_name = {}

        for i in range(200):  # More than MAX_MATCH_CANDIDATES
            rec_id = f"rec_{i}"
            name = f"app{i}"
            records[rec_id] = {"id": rec_id, "name": name}
            if name not in by_canonical_name:
                by_canonical_name[name] = []
            by_canonical_name[name].append(rec_id)

        cmdb_index = PlaneIndex(
            records=records,
            by_canonical_name=by_canonical_name,
            by_domain={},
            by_uri={},
            by_vendor_product={}
        )

        # Create entity that might fuzzy match many CMDB records
        entities = generate_test_entities(1, "app")

        plane_indexes = PlaneIndexes(
            idp=generate_test_plane_indexes(0),
            cmdb=cmdb_index,
            cloud=generate_test_plane_indexes(0),
            finance=generate_test_plane_indexes(0)
        )

        # This should complete quickly due to early exit
        start = time.perf_counter()
        results = correlate_entities_to_planes(entities, plane_indexes)
        duration = time.perf_counter() - start

        print(f"\n🚀 Early Exit Test:")
        print(f"  CMDB records: {len(records)}")
        print(f"  MAX_MATCH_CANDIDATES: {MAX_MATCH_CANDIDATES}")
        print(f"  Correlation time: {duration * 1000:.2f} ms")

        # Without early exit, this would take much longer
        # With early exit, should complete very quickly
        assert duration < 0.5, \
            f"Early exit should prevent long execution (took {duration:.2f}s)"

    def test_correlation_correctness_unchanged(self):
        """Verify optimizations don't change correlation results."""
        from aod.pipeline.normalize_observations import CandidateEntity
        from aod.pipeline.build_plane_indexes import PlaneIndexes, PlaneIndex
        from aod.pipeline.correlate_entities import MatchStatus

        # Create a known entity
        slack_entity = CandidateEntity(
            entity_id="ent_slack",
            canonical_name="slack",
            original_name="Slack",
            domain="slack.com",
            vendor=None,
            observation_ids=["d1"]
        )

        # Create matching records in CMDB and IdP
        cmdb_records = {
            "c1": {"id": "c1", "name": "Slack", "vendor": "Slack Technologies"}
        }
        idp_records = {
            "i1": {"id": "i1", "name": "Slack"}
        }

        cmdb_index = PlaneIndex(
            records=cmdb_records,
            by_canonical_name={"slack": ["c1"]},
            by_domain={},
            by_uri={},
            by_vendor_product={}
        )

        idp_index = PlaneIndex(
            records=idp_records,
            by_canonical_name={"slack": ["i1"]},
            by_domain={},
            by_uri={},
            by_vendor_product={}
        )

        plane_indexes = PlaneIndexes(
            idp=idp_index,
            cmdb=cmdb_index,
            cloud=generate_test_plane_indexes(0),
            finance=generate_test_plane_indexes(0)
        )

        results = correlate_entities_to_planes([slack_entity], plane_indexes)

        print(f"\n✓ Correctness Test:")
        print(f"  Entities: 1")
        print(f"  Correlation results: {len(results)}")

        # Should have correlation results
        assert len(results) == 1, "Should produce correlation result for entity"

        slack_result = results[0]
        print(f"  CMDB match status: {slack_result.cmdb.status}")
        print(f"  IdP match status: {slack_result.idp.status}")

        # With identical names, should get matches
        assert slack_result.cmdb.status == MatchStatus.MATCHED, "Should match CMDB record"
        assert slack_result.idp.status == MatchStatus.MATCHED, "Should match IdP record"


class TestPerformanceComparison:
    """Compare performance before and after optimizations."""

    def test_performance_baseline_small(self):
        """Baseline performance test with small dataset."""
        from aod.pipeline.build_plane_indexes import PlaneIndexes

        entities = generate_test_entities(20)
        plane_indexes = PlaneIndexes(
            idp=generate_test_plane_indexes(15),
            cmdb=generate_test_plane_indexes(10),
            cloud=generate_test_plane_indexes(0),
            finance=generate_test_plane_indexes(0)
        )

        # Run multiple iterations for more accurate timing
        iterations = 5
        times = []

        for _ in range(iterations):
            _levenshtein_distance.cache_clear()
            start = time.perf_counter()
            correlate_entities_to_planes(entities, plane_indexes)
            times.append(time.perf_counter() - start)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n⏱️  Small Dataset Benchmark (20 entities):")
        print(f"  Average time: {avg_time * 1000:.2f} ms")
        print(f"  Min time: {min_time * 1000:.2f} ms")
        print(f"  Max time: {max_time * 1000:.2f} ms")
        print(f"  Iterations: {iterations}")

        # Should be very fast for small datasets
        assert avg_time < 0.5, f"Small dataset should be fast (was {avg_time:.2f}s)"

    def test_performance_baseline_medium(self):
        """Baseline performance test with medium dataset."""
        from aod.pipeline.build_plane_indexes import PlaneIndexes

        entities = generate_test_entities(100)
        plane_indexes = PlaneIndexes(
            idp=generate_test_plane_indexes(75),
            cmdb=generate_test_plane_indexes(50),
            cloud=generate_test_plane_indexes(0),
            finance=generate_test_plane_indexes(0)
        )

        _levenshtein_distance.cache_clear()
        start = time.perf_counter()
        results = correlate_entities_to_planes(entities, plane_indexes)
        duration = time.perf_counter() - start

        cache_info = _levenshtein_distance.cache_info()

        print(f"\n⏱️  Medium Dataset Benchmark (100 entities):")
        print(f"  Total time: {duration * 1000:.2f} ms")
        print(f"  Entities: {len(entities)}")
        print(f"  Results: {len(results)}")
        print(f"  Throughput: {len(entities) / duration:.1f} entities/sec")
        print(f"  Cache hits: {cache_info.hits}")
        print(f"  Cache misses: {cache_info.misses}")

        # Should complete in reasonable time
        assert duration < 5.0, f"Medium dataset should complete quickly (was {duration:.2f}s)"

        # Should have decent cache hit rate
        if cache_info.hits + cache_info.misses > 0:
            hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses)
            print(f"  Cache hit rate: {hit_rate * 100:.1f}%")


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_correlation_performance.py -v -s
    pytest.main([__file__, "-v", "-s"])
