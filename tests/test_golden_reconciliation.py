"""
Golden Reconciliation Test - End-to-end accuracy benchmark

This test runs the full AOD pipeline against a curated Farm snapshot and
compares actual results against expected outcomes from Farm reconciliation.

GUARDRAILS - READ BEFORE MODIFYING:
====================================
1. NEVER CHANGE POLICY TO PASS A TEST
   - If tests fail, the code has bugs - fix the bugs, not the policy
   - Policy is defined by Farm/business requirements, not test outcomes
   
2. NEVER BREAK THE 'IRL' DYNAMIC TO PASS A TEST
   - Real-world behavior must be preserved
   - Tests validate reality, they don't define it
   
3. NO CHEATING - DO NOT FUDGE REALITY
   - No hardcoding expected values
   - No special-casing specific assets
   - No manipulating test fixtures to match broken code

If a test fails, investigate WHY the classification is wrong:
- Activity mismatch? (AOD vs Farm activity status)
- Governance mismatch? (AOD vs Farm IdP/CMDB detection)
- Finance mismatch? (AOD vs Farm ongoing finance detection)
- Domain key mismatch? (AOD has asset under different key)

METRICS MEASURED:
=================
- RECALL: What % of Farm's expected assets did we find?
- PRECISION: What % of our findings are actually correct?
- F1 SCORE: Harmonic mean of precision and recall
- FALSE NEGATIVES (Missed): Assets Farm expects that we didn't find
- FALSE POSITIVES: Assets we flagged that Farm didn't expect

THRESHOLDS:
===========
- Recall >= 95% per category
- Precision >= 90% per category (allows some false positives)
- Both must pass for the test to succeed

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
RECALL_THRESHOLD = 0.95
PRECISION_THRESHOLD = 0.90


def load_snapshot():
    """Load the real Farm snapshot fixture"""
    with open(FIXTURES_DIR / "real_farm_snapshot.json", "r") as f:
        return json.load(f)


def load_expected_outcomes():
    """Load the golden expected outcomes from Farm"""
    with open(FIXTURES_DIR / "golden_expected_outcomes.json", "r") as f:
        return json.load(f)


def compute_metrics(expected: set, actual: set, category: str) -> dict:
    """
    Compute comprehensive reconciliation metrics.
    
    Returns:
        dict with:
        - recall: matched / expected (sensitivity - did we catch what Farm expects?)
        - precision: matched / actual (are our findings correct?)
        - f1: harmonic mean of precision and recall
        - matched: true positives (correct classifications)
        - missed: false negatives (Farm expects, we didn't find)
        - false_positives: we found, Farm doesn't expect
    """
    matched = expected & actual
    missed = expected - actual  # False negatives
    false_positives = actual - expected  # False positives
    
    matched_count = len(matched)
    expected_count = len(expected)
    actual_count = len(actual)
    
    recall = matched_count / expected_count if expected_count > 0 else 1.0
    precision = matched_count / actual_count if actual_count > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "category": category,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "matched_count": matched_count,
        "missed_count": len(missed),
        "fp_count": len(false_positives),
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "matched": sorted(matched),
        "missed": sorted(missed),
        "false_positives": sorted(false_positives)
    }


def print_metrics_report(metrics: dict, recall_threshold: float, precision_threshold: float):
    """Print detailed metrics report for a category"""
    category = metrics['category'].upper()
    recall_status = "PASS" if metrics['recall'] >= recall_threshold else "FAIL"
    precision_status = "PASS" if metrics['precision'] >= precision_threshold else "FAIL"
    
    print(f"\n{category} CLASSIFICATION:")
    print(f"  Farm Expected: {metrics['expected_count']}")
    print(f"  AOD Found: {metrics['actual_count']}")
    print(f"  Matched (TP): {metrics['matched_count']}")
    print(f"  Missed (FN): {metrics['missed_count']}")
    print(f"  False Positives (FP): {metrics['fp_count']}")
    print(f"  ---")
    print(f"  RECALL: {metrics['recall']:.1%} [{recall_status}] (threshold: {recall_threshold:.0%})")
    print(f"  PRECISION: {metrics['precision']:.1%} [{precision_status}] (threshold: {precision_threshold:.0%})")
    print(f"  F1 SCORE: {metrics['f1']:.1%}")
    
    if metrics['missed']:
        print(f"  ---")
        print(f"  MISSED (FN) - Farm expects, AOD didn't find:")
        for asset in metrics['missed'][:20]:
            print(f"    - {asset}")
        if len(metrics['missed']) > 20:
            print(f"    ... and {len(metrics['missed']) - 20} more")
    
    if metrics['false_positives']:
        print(f"  ---")
        print(f"  FALSE POSITIVES (FP) - AOD found, Farm doesn't expect:")
        for asset in metrics['false_positives'][:20]:
            print(f"    - {asset}")
        if len(metrics['false_positives']) > 20:
            print(f"    ... and {len(metrics['false_positives']) - 20} more")


def run_pipeline_and_get_results():
    """Run the pipeline and return actual results - shared by all tests"""
    snapshot = load_snapshot()
    run_id = "golden_test"
    
    result = run_pipeline_ephemeral(
        snapshot,
        run_id=run_id,
        is_farm_source=True
    )
    
    if not result.success:
        raise RuntimeError(f"Pipeline failed: {result.error}")
    
    actual_results = emit_actual_results(
        run_id=run_id,
        assets=result.assets,
        activity_window_days=90,
        rejections=result.rejections,
        mode="sprawl",
        snapshot_as_of=result.snapshot_as_of
    )
    
    return actual_results


class TestGoldenReconciliation:
    """
    Golden reconciliation tests - validates end-to-end pipeline accuracy.
    
    REMINDER: If tests fail, fix the CODE not the POLICY.
    """
    
    def test_full_pipeline_accuracy(self):
        """
        Run full pipeline and validate accuracy in each category.
        
        PASS CRITERIA:
        - Recall >= 95% in EACH category (shadow, zombie)
        - Precision >= 90% in EACH category
        
        Recall measures: Did we find what Farm expects?
        Precision measures: Are our findings correct (not false positives)?
        
        GUARDRAIL: If this test fails, investigate the root cause.
        DO NOT change policy definitions to make tests pass.
        """
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_shadows = set(expected.get("expected_shadows", []))
        expected_zombies = set(expected.get("expected_zombies", []))
        
        actual_shadows = set(actual_results.shadow_actual)
        actual_zombies = set(actual_results.zombie_actual)
        
        shadow_metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
        zombie_metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")
        
        print("\n" + "=" * 80)
        print("GOLDEN RECONCILIATION TEST RESULTS")
        print("=" * 80)
        print("\nGUARDRAIL REMINDER: If tests fail, fix the CODE not the POLICY.")
        
        print_metrics_report(shadow_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)
        print_metrics_report(zombie_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)
        
        print("\n" + "=" * 80)
        
        failures = []
        
        if shadow_metrics['recall'] < RECALL_THRESHOLD:
            failures.append(
                f"Shadow RECALL {shadow_metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}. "
                f"Missed {shadow_metrics['missed_count']}: {shadow_metrics['missed'][:5]}..."
            )
        if shadow_metrics['precision'] < PRECISION_THRESHOLD:
            failures.append(
                f"Shadow PRECISION {shadow_metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}. "
                f"FPs {shadow_metrics['fp_count']}: {shadow_metrics['false_positives'][:5]}..."
            )
        
        if zombie_metrics['recall'] < RECALL_THRESHOLD:
            failures.append(
                f"Zombie RECALL {zombie_metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}. "
                f"Missed {zombie_metrics['missed_count']}: {zombie_metrics['missed'][:5]}..."
            )
        if zombie_metrics['precision'] < PRECISION_THRESHOLD:
            failures.append(
                f"Zombie PRECISION {zombie_metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}. "
                f"FPs {zombie_metrics['fp_count']}: {zombie_metrics['false_positives'][:5]}..."
            )
        
        if failures:
            pytest.fail(
                "\n\nRECONCILIATION ACCURACY FAILURE\n"
                "================================\n"
                "REMINDER: Fix the CODE, not the POLICY.\n\n" +
                "\n".join(failures)
            )
    
    def test_shadow_recall(self):
        """Shadow recall must be >= 95%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_shadows = set(expected.get("expected_shadows", []))
        actual_shadows = set(actual_results.shadow_actual)
        
        metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
        
        assert metrics['recall'] >= RECALL_THRESHOLD, (
            f"Shadow RECALL {metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed']}"
        )
    
    def test_shadow_precision(self):
        """Shadow precision must be >= 90%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_shadows = set(expected.get("expected_shadows", []))
        actual_shadows = set(actual_results.shadow_actual)
        
        metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
        
        assert metrics['precision'] >= PRECISION_THRESHOLD, (
            f"Shadow PRECISION {metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}. "
            f"False positives: {metrics['false_positives']}"
        )
    
    def test_zombie_recall(self):
        """Zombie recall must be >= 95%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_zombies = set(expected.get("expected_zombies", []))
        actual_zombies = set(actual_results.zombie_actual)
        
        metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")
        
        assert metrics['recall'] >= RECALL_THRESHOLD, (
            f"Zombie RECALL {metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed']}"
        )
    
    def test_zombie_precision(self):
        """Zombie precision must be >= 90%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_zombies = set(expected.get("expected_zombies", []))
        actual_zombies = set(actual_results.zombie_actual)
        
        metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")
        
        assert metrics['precision'] >= PRECISION_THRESHOLD, (
            f"Zombie PRECISION {metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}. "
            f"False positives: {metrics['false_positives']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
