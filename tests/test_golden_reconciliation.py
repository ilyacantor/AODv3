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

CATEGORIES TESTED:
==================
- ADMISSION: Cataloged (admitted) and Rejected assets
- CLASSIFICATION: Shadow and Zombie assets

THRESHOLDS:
===========
- Admission: Recall >= 95%, Precision >= 95% (stricter - admission is upstream)
- Classification: Recall >= 95%, Precision >= 90% (allows some false positives)
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

# Classification thresholds (shadow, zombie)
RECALL_THRESHOLD = 0.95
PRECISION_THRESHOLD = 0.90

# Admission thresholds (cataloged, rejected) - stricter because admission is upstream
ADMISSION_RECALL_THRESHOLD = 0.95
ADMISSION_PRECISION_THRESHOLD = 0.95


def load_snapshot():
    """Load the real Farm snapshot fixture"""
    with open(FIXTURES_DIR / "real_farm_snapshot.json", "r") as f:
        return json.load(f)


def load_expected_outcomes():
    """Load the golden expected outcomes from Farm"""
    with open(FIXTURES_DIR / "golden_expected_outcomes.json", "r") as f:
        return json.load(f)


def normalize_rejected_key(key: str) -> str:
    """
    Normalize a rejected asset key for comparison.
    
    - Strips 'entity:' prefix (AOD uses this internally)
    - Returns lowercase for case-insensitive matching
    """
    k = key.lower()
    while k.startswith("entity:"):
        k = k[7:]  # len("entity:") = 7
    return k


def is_domain_key(key: str) -> bool:
    """
    Check if a key looks like a domain (has a dot and TLD).
    
    Farm's expected_rejected includes both:
    - Domains: "0kta.com", "miro.com"  
    - Artifact IDs: "ads168", "adserver207" (non-domain entity names)
    
    We only compare domain-based rejections since AOD normalizes to domains.
    """
    return '.' in key and not key.startswith('.')


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
        expected_cataloged = set(expected.get("expected_cataloged", []))
        # Filter rejected to domain-only (Farm includes artifact IDs that AOD doesn't track)
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
        
        shadow_metrics = compute_metrics(expected_shadows, actual_shadows, "shadow")
        zombie_metrics = compute_metrics(expected_zombies, actual_zombies, "zombie")
        cataloged_metrics = compute_metrics(expected_cataloged, actual_cataloged, "cataloged")
        rejected_metrics = compute_metrics(expected_rejected, actual_rejected, "rejected")
        
        print("\n" + "=" * 80)
        print("GOLDEN RECONCILIATION TEST RESULTS")
        print("=" * 80)
        print("\nGUARDRAIL REMINDER: If tests fail, fix the CODE not the POLICY.")
        
        print("\n--- ADMISSION ---")
        print_metrics_report(cataloged_metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)
        print_metrics_report(rejected_metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)
        
        print("\n--- CLASSIFICATION ---")
        print_metrics_report(shadow_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)
        print_metrics_report(zombie_metrics, RECALL_THRESHOLD, PRECISION_THRESHOLD)
        
        print("\n" + "=" * 80)
        
        failures = []
        
        # Admission failures
        if cataloged_metrics['recall'] < ADMISSION_RECALL_THRESHOLD:
            failures.append(
                f"Cataloged RECALL {cataloged_metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}. "
                f"Missed {cataloged_metrics['missed_count']}: {cataloged_metrics['missed'][:5]}..."
            )
        if cataloged_metrics['precision'] < ADMISSION_PRECISION_THRESHOLD:
            failures.append(
                f"Cataloged PRECISION {cataloged_metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}. "
                f"FPs {cataloged_metrics['fp_count']}: {cataloged_metrics['false_positives'][:5]}..."
            )
        
        if rejected_metrics['recall'] < ADMISSION_RECALL_THRESHOLD:
            failures.append(
                f"Rejected RECALL {rejected_metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}. "
                f"Missed {rejected_metrics['missed_count']}: {rejected_metrics['missed'][:5]}..."
            )
        if rejected_metrics['precision'] < ADMISSION_PRECISION_THRESHOLD:
            failures.append(
                f"Rejected PRECISION {rejected_metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}. "
                f"FPs {rejected_metrics['fp_count']}: {rejected_metrics['false_positives'][:5]}..."
            )
        
        # Classification failures
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
    
    # =========================================================================
    # ADMISSION TESTS - Cataloged and Rejected
    # =========================================================================
    
    def test_cataloged_recall(self):
        """Cataloged (admitted) recall must be >= 95%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_cataloged = set(expected.get("expected_cataloged", []))
        actual_cataloged = set(
            k for k, v in actual_results.admission_actual.items() 
            if v == "admitted"
        )
        
        metrics = compute_metrics(expected_cataloged, actual_cataloged, "cataloged")
        
        print_metrics_report(metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)
        
        assert metrics['recall'] >= ADMISSION_RECALL_THRESHOLD, (
            f"Cataloged RECALL {metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed'][:10]}..."
        )
    
    def test_cataloged_precision(self):
        """Cataloged (admitted) precision must be >= 95%"""
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        expected_cataloged = set(expected.get("expected_cataloged", []))
        actual_cataloged = set(
            k for k, v in actual_results.admission_actual.items() 
            if v == "admitted"
        )
        
        metrics = compute_metrics(expected_cataloged, actual_cataloged, "cataloged")
        
        assert metrics['precision'] >= ADMISSION_PRECISION_THRESHOLD, (
            f"Cataloged PRECISION {metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}. "
            f"False positives: {metrics['false_positives'][:10]}..."
        )
    
    def test_rejected_recall(self):
        """
        Rejected recall must be >= 95% (domain-level only).
        
        NOTE: Farm's expected_rejected includes both domains and artifact IDs.
        AOD normalizes to domains, so we only compare domain-based rejections.
        Artifact ID delta is logged but not asserted.
        """
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        # Filter to domain-only and normalize keys
        expected_rejected = set(
            k.lower() for k in expected.get("expected_rejected", [])
            if is_domain_key(k)
        )
        actual_rejected = set(
            normalize_rejected_key(k) for k, v in actual_results.admission_actual.items() 
            if v == "rejected"
        )
        
        # Log artifact delta (informational only)
        artifact_ids = [k for k in expected.get("expected_rejected", []) if not is_domain_key(k)]
        if artifact_ids:
            print(f"\n  INFO: {len(artifact_ids)} non-domain artifact IDs in Farm's rejected list (not compared)")
        
        metrics = compute_metrics(expected_rejected, actual_rejected, "rejected (domains)")
        
        print_metrics_report(metrics, ADMISSION_RECALL_THRESHOLD, ADMISSION_PRECISION_THRESHOLD)
        
        assert metrics['recall'] >= ADMISSION_RECALL_THRESHOLD, (
            f"Rejected RECALL {metrics['recall']:.1%} < {ADMISSION_RECALL_THRESHOLD:.0%}. "
            f"Missed: {metrics['missed'][:10]}..."
        )
    
    def test_rejected_precision(self):
        """
        Rejected precision must be >= 95% (domain-level only).
        
        NOTE: We only compare domain-based rejections since AOD normalizes to domains.
        """
        expected = load_expected_outcomes()
        actual_results = run_pipeline_and_get_results()
        
        # Filter to domain-only and normalize keys
        expected_rejected = set(
            k.lower() for k in expected.get("expected_rejected", [])
            if is_domain_key(k)
        )
        actual_rejected = set(
            normalize_rejected_key(k) for k, v in actual_results.admission_actual.items() 
            if v == "rejected"
        )
        
        metrics = compute_metrics(expected_rejected, actual_rejected, "rejected (domains)")
        
        assert metrics['precision'] >= ADMISSION_PRECISION_THRESHOLD, (
            f"Rejected PRECISION {metrics['precision']:.1%} < {ADMISSION_PRECISION_THRESHOLD:.0%}. "
            f"False positives: {metrics['false_positives'][:10]}..."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
