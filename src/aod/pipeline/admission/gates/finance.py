"""Finance admission gate - check Finance plane criteria."""

from ...correlate_entities import CorrelationResult, MatchStatus
from ....models.input_contracts import Contract, Transaction


def has_recurring_finance_spend(correlation: CorrelationResult) -> bool:
    """
    Check if the correlation has recurring finance spend (ongoing finance).

    Returns True if there are:
    - Recurring contracts with amount > 0, OR
    - Recurring transactions with amount > 0

    NOTE: Multiple non-recurring transactions do NOT qualify as recurring spend.
    Only explicitly marked is_recurring=True records count as ongoing finance.

    This is used by the admission policy to allow finance-only admission
    when there's strong recurring spend evidence combined with recent activity.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False

    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            if record.is_recurring and record.amount > 0:
                return True
        elif isinstance(record, Transaction):
            if record.is_recurring and record.amount > 0:
                return True

    return False


def check_finance_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Finance plane admission criteria:
    - Finance match with any spend evidence
    - Prefer: recurring contracts/transactions (stronger signal)

    RELAXED: Any finance match with amount > 0 counts for admission.
    Recurring spend provides stronger confidence but is not required.

    NOTE: Both MATCHED and AMBIGUOUS count as having finance evidence.
    Vendor-only matches are NOT sufficient for finance admission.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    # Check for actual finance records (Contract or Transaction)
    has_actual_finance_record = False
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            has_actual_finance_record = True
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring contract ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Contract ${record.amount}"
        elif isinstance(record, Transaction):
            has_actual_finance_record = True
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring transaction ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Transaction ${record.amount}"

    # If we found Contract/Transaction records (even with amount=0), admit
    if has_actual_finance_record:
        return True, "Finance match (spend evidence)"

    # Check match_method - only trust non-vendor finance matches
    # Vendor-only matches don't indicate actual finance evidence
    if correlation.finance.match_method and correlation.finance.match_method != "vendor":
        return True, "Finance match (correlation status)"

    # Vendor-only match or empty records - not sufficient for finance admission
    return False, ""
