"""
Golden Reconciliation Test - End-to-end accuracy benchmark

This test runs the full AOD pipeline against a curated Farm snapshot and
compares actual results against expected outcomes from Farm reconciliation.

THRESHOLD: 95%+ accuracy in EACH category (shadow, zombie)
for the test to pass.

Usage:
    pytest tests/test_golden_reconciliation.py -v
    
To debug specific assets:
    DEBUG_RECONCILE_ASSETS=fasthub.dev,amazon.com pytest tests/test_golden_reconciliation.py -v -s
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.pipeline.pipeline_executor import run_pipeline_ephemeral
from aod.pipeline.aod_agent_reconcile import emit_actual_results


FIXTURES_DIR = Path(__file__).parent / "fixtures"
ACCURACY_THRESHOLD = 0.95


def load_snapshot():
    """Load the real Farm snapshot fixture"""
    with open(FIXTURES_DIR / "real_farm_snapshot.json", "r") as f:
        return json.load(f)


def load_expected_outcomes():
    """Load the golden expected outcomes from Farm"""
    with open(FIXTURES_DIR / "golden_expected_outcomes.json", "r") as f:
        return json.load(f)


def compute_accuracy(expected: set, actual: set) -> dict:
    """Compute reconciliation accuracy metrics"""
    matched = expected & actual
    missed = expected - actual
    false_positives = actual - expected
    
    total_expected = len(expected)
    matched_count = len(matched)
    
    accuracy = matched_count / total_expected if total_expected > 0 else 1.0
    
    return {
        "expected_count": total_expected,
        "actual_count": len(actual),
        "matched_count": matched_count,
        "missed_count": len(missed),
        "fp_count": len(false_positives),
        "accuracy": accuracy,
        "matched": sorted(matched),
        "missed": sorted(missed),
        "false_positives": sorted(false_positives)
    }


class TestGoldenReconciliation:
    """Golden reconciliation tests - validates end-to-end pipeline accuracy"""
    
    def test_full_pipeline_accuracy(self):
        """
        Run full pipeline and validate accuracy in each category.
        
        PASS CRITERIA: 95%+ accuracy in EACH of:
        - Shadow classification
        - Zombie classification
        
        This test will fail if ANY category falls below 95%.
        """
        snapshot = load_snapshot()
        expected = load_expected_outcomes()
        
        run_id = "golden_test"
        
        result = run_pipeline_ephemeral(
            snapshot,
            run_id=run_id,
            is_farm_source=True
        )
        
        assert result.success, f"Pipeline failed: {result.error}"
        
        actual_results = emit_actual_results(
            run_id=run_id,
            assets=result.assets,
            activity_window_days=90,
            rejections=result.rejections,
            mode="sprawl",
            snapshot_as_of=result.snapshot_as_of
        )
        
        expected_shadows = set(expected.get("expected_shadows", []))
        expected_zombies = set(expected.get("expected_zombies", []))
        
        actual_shadows = set(actual_results.shadow_actual)
        actual_zombies = set(actual_results.zombie_actual)
        
        shadow_metrics = compute_accuracy(expected_shadows, actual_shadows)
        zombie_metrics = compute_accuracy(expected_zombies, actual_zombies)
        
        print("\n" + "=" * 80)
        print("GOLDEN RECONCILIATION TEST RESULTS")
        print("=" * 80)
        
        print(f"\nSHADOW CLASSIFICATION:")
        print(f"  Expected: {shadow_metrics['expected_count']}")
        print(f"  Found: {shadow_metrics['actual_count']}")
        print(f"  Matched: {shadow_metrics['matched_count']}")
        print(f"  Missed: {shadow_metrics['missed_count']}")
        print(f"  False Positives: {shadow_metrics['fp_count']}")
        print(f"  ACCURACY: {shadow_metrics['accuracy']:.1%}")
        if shadow_metrics['missed']:
            print(f"  Missed assets: {shadow_metrics['missed']}")
        if shadow_metrics['false_positives'][:10]:
            print(f"  FP assets (first 10): {shadow_metrics['false_positives'][:10]}")
        
        print(f"\nZOMBIE CLASSIFICATION:")
        print(f"  Expected: {zombie_metrics['expected_count']}")
        print(f"  Found: {zombie_metrics['actual_count']}")
        print(f"  Matched: {zombie_metrics['matched_count']}")
        print(f"  Missed: {zombie_metrics['missed_count']}")
        print(f"  False Positives: {zombie_metrics['fp_count']}")
        print(f"  ACCURACY: {zombie_metrics['accuracy']:.1%}")
        if zombie_metrics['missed']:
            print(f"  Missed assets: {zombie_metrics['missed']}")
        if zombie_metrics['false_positives'][:10]:
            print(f"  FP assets (first 10): {zombie_metrics['false_positives'][:10]}")
        
        print("\n" + "=" * 80)
        
        failures = []
        if shadow_metrics['accuracy'] < ACCURACY_THRESHOLD:
            failures.append(
                f"Shadow accuracy {shadow_metrics['accuracy']:.1%} < {ACCURACY_THRESHOLD:.0%} threshold. "
                f"Missed: {shadow_metrics['missed']}"
            )
        if zombie_metrics['accuracy'] < ACCURACY_THRESHOLD:
            failures.append(
                f"Zombie accuracy {zombie_metrics['accuracy']:.1%} < {ACCURACY_THRESHOLD:.0%} threshold. "
                f"Missed: {zombie_metrics['missed']}"
            )
        
        if failures:
            pytest.fail("\n".join(failures))
    
    def test_shadow_accuracy_detailed(self):
        """Detailed shadow accuracy test with diagnostic output"""
        snapshot = load_snapshot()
        expected = load_expected_outcomes()
        
        run_id = "shadow_test"
        
        result = run_pipeline_ephemeral(
            snapshot,
            run_id=run_id,
            is_farm_source=True
        )
        
        assert result.success, f"Pipeline failed: {result.error}"
        
        actual_results = emit_actual_results(
            run_id=run_id,
            assets=result.assets,
            activity_window_days=90,
            rejections=result.rejections,
            mode="sprawl",
            snapshot_as_of=result.snapshot_as_of
        )
        
        expected_shadows = set(expected.get("expected_shadows", []))
        actual_shadows = set(actual_results.shadow_actual)
        
        metrics = compute_accuracy(expected_shadows, actual_shadows)
        
        assert metrics['accuracy'] >= ACCURACY_THRESHOLD, (
            f"Shadow accuracy {metrics['accuracy']:.1%} below {ACCURACY_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed']}"
        )
    
    def test_zombie_accuracy_detailed(self):
        """Detailed zombie accuracy test with diagnostic output"""
        snapshot = load_snapshot()
        expected = load_expected_outcomes()
        
        run_id = "zombie_test"
        
        result = run_pipeline_ephemeral(
            snapshot,
            run_id=run_id,
            is_farm_source=True
        )
        
        assert result.success, f"Pipeline failed: {result.error}"
        
        actual_results = emit_actual_results(
            run_id=run_id,
            assets=result.assets,
            activity_window_days=90,
            rejections=result.rejections,
            mode="sprawl",
            snapshot_as_of=result.snapshot_as_of
        )
        
        expected_zombies = set(expected.get("expected_zombies", []))
        actual_zombies = set(actual_results.zombie_actual)
        
        metrics = compute_accuracy(expected_zombies, actual_zombies)
        
        assert metrics['accuracy'] >= ACCURACY_THRESHOLD, (
            f"Zombie accuracy {metrics['accuracy']:.1%} below {ACCURACY_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
