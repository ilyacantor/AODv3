"""
Regression gate for reconciliation - prevents regressions in shadow/zombie classification.

This module implements CI-style validation to catch regressions:
1. KEY_NORMALIZATION_MISMATCH count must not increase
2. Previously-fixed domain patterns must not reappear
3. Matched count fluctuation is allowed within tolerance

Usage:
    gate_result = validate_reconciliation_regression(new_result, baseline)
    if not gate_result.passed:
        raise RegressionError(gate_result.failures)
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


KNOWN_FIXED_PATTERNS = [
    "slack.com",
    "salesforce.com",
    "notion.so",
    "zoom.us",
    "dropbox.com",
]


@dataclass
class RegressionGateResult:
    """Result of regression gate validation"""
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    baseline_matched: int = 0
    baseline_missed: int = 0
    baseline_key_mismatches: int = 0
    
    current_matched: int = 0
    current_missed: int = 0
    current_key_mismatches: int = 0
    
    matched_delta: int = 0
    missed_delta: int = 0
    key_mismatch_delta: int = 0


@dataclass
class ReconciliationBaseline:
    """Baseline reconciliation metrics for comparison"""
    snapshot_id: str
    timestamp: datetime
    matched_count: int
    missed_count: int
    key_normalization_mismatch_count: int
    fixed_patterns: list[str] = field(default_factory=list)
    
    @classmethod
    def from_reconcile_result(cls, result: dict) -> "ReconciliationBaseline":
        """Create baseline from reconciliation result"""
        differences = result.get("differences", [])
        
        matched_count = sum(1 for d in differences if d.get("result") == "matched")
        missed_count = sum(1 for d in differences if d.get("result") == "missed")
        
        key_mismatch_count = sum(
            1 for d in differences 
            if "KEY_NORMALIZATION_MISMATCH" in d.get("rca_hint", "")
        )
        
        return cls(
            snapshot_id=result.get("snapshot_id", "unknown"),
            timestamp=datetime.now(timezone.utc),
            matched_count=matched_count,
            missed_count=missed_count,
            key_normalization_mismatch_count=key_mismatch_count
        )


def count_key_normalization_mismatches(differences: list[dict]) -> int:
    """Count KEY_NORMALIZATION_MISMATCH errors in differences"""
    return sum(
        1 for d in differences 
        if "KEY_NORMALIZATION" in (d.get("rca_hint", "") or "").upper()
        or "KEY_MISMATCH" in (d.get("rca_hint", "") or "").upper()
        or "NORMALIZATION_MISMATCH" in (d.get("headline", "") or "").upper()
    )


def count_matched(differences: list[dict]) -> int:
    """Count matched assets in differences"""
    return sum(1 for d in differences if d.get("result") == "matched")


def count_missed(differences: list[dict]) -> int:
    """Count missed assets in differences"""
    return sum(1 for d in differences if d.get("result") == "missed")


def find_reappearing_fixed_patterns(
    differences: list[dict], 
    fixed_patterns: list[str] | None = None
) -> list[str]:
    """Find previously-fixed domain patterns that have reappeared as misses"""
    patterns_to_check = fixed_patterns or KNOWN_FIXED_PATTERNS
    reappeared = []
    
    for diff in differences:
        if diff.get("result") != "missed":
            continue
        
        asset_key = (diff.get("asset_key", "") or "").lower()
        rca_hint = diff.get("rca_hint", "") or ""
        
        for pattern in patterns_to_check:
            if pattern.lower() in asset_key:
                if "KEY_NORMALIZATION" in rca_hint.upper():
                    reappeared.append(f"{asset_key} (pattern: {pattern})")
    
    return reappeared


def validate_reconciliation_regression(
    current_result: dict,
    baseline: ReconciliationBaseline | None = None,
    max_key_mismatch_increase: int = 0,
    matched_tolerance_percent: float = 5.0
) -> RegressionGateResult:
    """
    Validate that reconciliation result doesn't regress from baseline.
    
    Rules:
    1. KEY_NORMALIZATION_MISMATCH count must not increase (hard fail)
    2. Previously-fixed domain patterns must not reappear (hard fail)
    3. Matched count can fluctuate within tolerance (warning only)
    4. Missed count increase generates warning
    
    Args:
        current_result: Current reconciliation result dict
        baseline: Optional baseline to compare against. If None, only checks fixed patterns.
        max_key_mismatch_increase: Maximum allowed increase in key mismatches (default 0)
        matched_tolerance_percent: Percentage tolerance for matched count fluctuation
    
    Returns:
        RegressionGateResult with pass/fail status and details
    """
    differences = current_result.get("differences", [])
    
    current_matched = count_matched(differences)
    current_missed = count_missed(differences)
    current_key_mismatches = count_key_normalization_mismatches(differences)
    
    failures = []
    warnings = []
    
    reappeared = find_reappearing_fixed_patterns(differences)
    if reappeared:
        failures.append(
            f"REGRESSION: Previously-fixed patterns reappeared as KEY_NORMALIZATION_MISMATCH: "
            f"{', '.join(reappeared[:5])}"
            + (f" (+{len(reappeared) - 5} more)" if len(reappeared) > 5 else "")
        )
    
    baseline_matched = 0
    baseline_missed = 0
    baseline_key_mismatches = 0
    matched_delta = 0
    missed_delta = 0
    key_mismatch_delta = 0
    
    if baseline:
        baseline_matched = baseline.matched_count
        baseline_missed = baseline.missed_count
        baseline_key_mismatches = baseline.key_normalization_mismatch_count
        
        key_mismatch_delta = current_key_mismatches - baseline_key_mismatches
        if key_mismatch_delta > max_key_mismatch_increase:
            failures.append(
                f"REGRESSION: KEY_NORMALIZATION_MISMATCH count increased from "
                f"{baseline_key_mismatches} to {current_key_mismatches} "
                f"(+{key_mismatch_delta}, max allowed: +{max_key_mismatch_increase})"
            )
        
        matched_delta = current_matched - baseline_matched
        tolerance = int(baseline_matched * matched_tolerance_percent / 100)
        if abs(matched_delta) > tolerance:
            if matched_delta < 0:
                warnings.append(
                    f"Matched count decreased from {baseline_matched} to {current_matched} "
                    f"({matched_delta}, beyond {matched_tolerance_percent}% tolerance)"
                )
            else:
                warnings.append(
                    f"Matched count increased significantly from {baseline_matched} to "
                    f"{current_matched} (+{matched_delta})"
                )
        
        missed_delta = current_missed - baseline_missed
        if missed_delta > 0:
            warnings.append(
                f"Missed count increased from {baseline_missed} to {current_missed} "
                f"(+{missed_delta})"
            )
    
    passed = len(failures) == 0
    
    return RegressionGateResult(
        passed=passed,
        failures=failures,
        warnings=warnings,
        baseline_matched=baseline_matched,
        baseline_missed=baseline_missed,
        baseline_key_mismatches=baseline_key_mismatches,
        current_matched=current_matched,
        current_missed=current_missed,
        current_key_mismatches=current_key_mismatches,
        matched_delta=matched_delta,
        missed_delta=missed_delta,
        key_mismatch_delta=key_mismatch_delta
    )


def format_gate_report(result: RegressionGateResult) -> str:
    """Format regression gate result as human-readable report"""
    lines = []
    
    if result.passed:
        lines.append("REGRESSION GATE: PASSED")
    else:
        lines.append("REGRESSION GATE: FAILED")
    
    lines.append("")
    lines.append("Metrics:")
    lines.append(f"  Matched: {result.current_matched} (delta: {result.matched_delta:+d})")
    lines.append(f"  Missed: {result.current_missed} (delta: {result.missed_delta:+d})")
    lines.append(f"  Key Mismatches: {result.current_key_mismatches} (delta: {result.key_mismatch_delta:+d})")
    
    if result.failures:
        lines.append("")
        lines.append("FAILURES:")
        for f in result.failures:
            lines.append(f"  - {f}")
    
    if result.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        for w in result.warnings:
            lines.append(f"  - {w}")
    
    return "\n".join(lines)
