#!/usr/bin/env python3
"""
Baseline Reconciliation Test - Run without pytest
Measures current KEY_NORMALIZATION_MISMATCH errors before Phase 1 fix
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aod.pipeline.pipeline_executor import run_pipeline_ephemeral
from aod.pipeline.aod_agent_reconcile import emit_actual_results


def load_snapshot():
    """Load the real Farm snapshot fixture"""
    with open("tests/fixtures/real_farm_snapshot.json", "r") as f:
        return json.load(f)


def load_expected_outcomes():
    """Load the golden expected outcomes from Farm"""
    with open("tests/fixtures/golden_expected_outcomes.json", "r") as f:
        return json.load(f)


def compute_metrics(expected: set, actual: set, category: str) -> dict:
    """Compute comprehensive reconciliation metrics"""
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


def main():
    print("=" * 80)
    print("BASELINE RECONCILIATION TEST - BEFORE PHASE 1 FIX")
    print("=" * 80)
    print("\nThis test measures current KEY_NORMALIZATION_MISMATCH errors")
    print("Target thresholds: Recall >= 95%, Precision >= 90%\n")

    # Load expected outcomes from Farm
    expected = load_expected_outcomes()
    expected_shadows = set(expected.get("expected_shadows", []))
    expected_zombies = set(expected.get("expected_zombies", []))

    print(f"Loading Farm snapshot...")
    snapshot = load_snapshot()

    print(f"Running AOD pipeline...")
    run_id = "baseline_test"

    try:
        result = run_pipeline_ephemeral(
            snapshot,
            run_id=run_id,
            is_farm_source=True
        )

        if not result.success:
            print(f"ERROR: Pipeline failed: {result.error}")
            return 1

        print(f"Pipeline succeeded: {len(result.assets)} assets created")

        actual_results = emit_actual_results(
            run_id=run_id,
            assets=result.assets,
            activity_window_days=90,
            rejections=result.rejections,
            mode="sprawl",
            snapshot_as_of=result.snapshot_as_of
        )

        actual_shadows = set(actual_results.shadow_actual)
        actual_zombies = set(actual_results.zombie_actual)

        print(f"\nAOD classified:")
        print(f"  Shadows: {len(actual_shadows)}")
        print(f"  Zombies: {len(actual_zombies)}")

        # Compute metrics
        shadow_metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
        zombie_metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")

        # Print detailed reports
        print("\n" + "=" * 80)
        print_metrics_report(shadow_metrics, 0.95, 0.90)
        print_metrics_report(zombie_metrics, 0.95, 0.90)
        print("\n" + "=" * 80)

        # Check if we pass thresholds
        shadow_pass = shadow_metrics['recall'] >= 0.95 and shadow_metrics['precision'] >= 0.90
        zombie_pass = zombie_metrics['recall'] >= 0.95 and zombie_metrics['precision'] >= 0.90

        if shadow_pass and zombie_pass:
            print("\nOVERALL: PASS ✓")
            print("No KEY_NORMALIZATION_MISMATCH issues detected!")
            return 0
        else:
            print("\nOVERALL: FAIL ✗")
            print("\nKEY_NORMALIZATION_MISMATCH issues detected:")
            if not shadow_pass:
                print(f"  - Shadow classification below threshold")
            if not zombie_pass:
                print(f"  - Zombie classification below threshold")

            print("\nProceeding with Phase 1 fix...")
            return 1

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
