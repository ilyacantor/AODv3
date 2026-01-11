"""Run golden reconciliation test and display results"""
import sys
sys.path.insert(0, 'src')

import json
from pathlib import Path
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral
from aod.pipeline.aod_agent_reconcile import emit_actual_results

FIXTURES_DIR = Path("tests/fixtures")

# Classification thresholds
RECALL_THRESHOLD = 0.95
PRECISION_THRESHOLD = 0.90
ADMISSION_RECALL_THRESHOLD = 0.95
ADMISSION_PRECISION_THRESHOLD = 0.95


def load_snapshot():
    with open(FIXTURES_DIR / "real_farm_snapshot.json", "r") as f:
        return json.load(f)


def load_expected_outcomes():
    with open(FIXTURES_DIR / "golden_expected_outcomes.json", "r") as f:
        return json.load(f)


def normalize_rejected_key(key: str) -> str:
    k = key.lower()
    while k.startswith("entity:"):
        k = k[7:]
    return k


def is_domain_key(key: str) -> bool:
    return '.' in key and not key.startswith('.')


def compute_metrics(expected: set, actual: set, category: str) -> dict:
    matched = expected & actual
    missed = expected - actual
    false_positives = actual - expected

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
    category = metrics['category'].upper()
    recall_status = "✅ PASS" if metrics['recall'] >= recall_threshold else "❌ FAIL"
    precision_status = "✅ PASS" if metrics['precision'] >= precision_threshold else "❌ FAIL"

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
    print("Loading snapshot and expected outcomes...")
    snapshot = load_snapshot()
    expected = load_expected_outcomes()

    print("Running pipeline...")
    run_id = "golden_test"
    result = run_pipeline_ephemeral(
        snapshot,
        run_id=run_id,
        is_farm_source=True
    )

    if not result.success:
        print(f"❌ Pipeline failed: {result.error}")
        return 1

    print("Emitting results...")
    actual_results = emit_actual_results(
        run_id=run_id,
        assets=result.assets,
        activity_window_days=90,
        rejections=result.rejections,
        mode="sprawl",
        snapshot_as_of=result.snapshot_as_of
    )

    # Extract expected and actual sets
    expected_shadows = set(expected.get("expected_shadows", []))
    expected_zombies = set(expected.get("expected_zombies", []))
    expected_cataloged = set(expected.get("expected_cataloged", []))
    expected_rejected = set(
        k.lower() for k in expected.get("expected_rejected", [])
        if is_domain_key(k)
    )

    actual_shadows = set(actual_results.shadow_actual)
    actual_zombies = set(actual_results.zombie_actual)
    actual_cataloged = set(
        k for k, v in actual_results.admission_actual.items()
        if v == "admitted"
    )
    actual_rejected = set(
        normalize_rejected_key(k) for k, v in actual_results.admission_actual.items()
        if v == "rejected"
    )

    # Compute metrics
    shadow_metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
    zombie_metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")
    cataloged_metrics = compute_metrics(expected_cataloged, actual_cataloged, "cataloged")
    rejected_metrics = compute_metrics(expected_rejected, actual_rejected, "rejected")

    # Print report
    print("\n" + "=" * 80)
    print("GOLDEN RECONCILIATION TEST RESULTS")
    print("=" * 80)

    print("\n--- ADMISSION ---")
    print_metrics_report(cataloged_metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)
    print_metrics_report(rejected_metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)

    print("\n--- CLASSIFICATION ---")
    print_metrics_report(shadow_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)
    print_metrics_report(zombie_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)

    print("\n" + "=" * 80)

    # Check for failures
    failures = []

    if cataloged_metrics['recall'] < ADMISSION_RECALL_THRESHOLD:
        failures.append(f"Cataloged RECALL {cataloged_metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}")
    if cataloged_metrics['precision'] < ADMISSION_PRECISION_THRESHOLD:
        failures.append(f"Cataloged PRECISION {cataloged_metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}")

    if rejected_metrics['recall'] < ADMISSION_RECALL_THRESHOLD:
        failures.append(f"Rejected RECALL {rejected_metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}")
    if rejected_metrics['precision'] < ADMISSION_PRECISION_THRESHOLD:
        failures.append(f"Rejected PRECISION {rejected_metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}")

    if shadow_metrics['recall'] < RECALL_THRESHOLD:
        failures.append(f"Shadow RECALL {shadow_metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}")
    if shadow_metrics['precision'] < PRECISION_THRESHOLD:
        failures.append(f"Shadow PRECISION {shadow_metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}")

    if zombie_metrics['recall'] < RECALL_THRESHOLD:
        failures.append(f"Zombie RECALL {zombie_metrics['recall']:.1%} < {RECALL_THRESHOLD:.0%}")
    if zombie_metrics['precision'] < PRECISION_THRESHOLD:
        failures.append(f"Zombie PRECISION {zombie_metrics['precision']:.1%} < {PRECISION_THRESHOLD:.0%}")

    if failures:
        print("\n❌ TEST FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    else:
        print("\n✅ ALL TESTS PASSED!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
