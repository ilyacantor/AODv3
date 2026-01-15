"""Utility functions for run-related routes"""

from typing import Optional
from datetime import datetime, timezone


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    """Parse an ISO datetime string, handling various formats."""
    if not dt_str:
        return None
    try:
        dt_str = dt_str.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(dt_str)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def parse_snapshot_generated_at(snapshot_data: dict) -> Optional[datetime]:
    """Parse generated_at/created_at from snapshot meta for recency calculation.

    Checks multiple sources in priority order:
    1. generated_at (Farm adapter normalized field)
    2. created_at (raw Farm meta field)
    """
    try:
        meta = snapshot_data.get("meta", {})

        generated_at_str = meta.get("generated_at")
        if generated_at_str:
            result = parse_iso_datetime(generated_at_str)
            if result:
                return result

        created_at_str = meta.get("created_at")
        if created_at_str:
            result = parse_iso_datetime(created_at_str)
            if result:
                return result
    except (ValueError, TypeError):
        pass
    return None


def get_run_snapshot_as_of(run) -> Optional[datetime]:
    """Extract snapshot_as_of from run.input_meta for activity recency calculation.

    Critical for zombie detection accuracy: ensures activity status (RECENT/STALE)
    is calculated relative to the snapshot's generated_at time, not wall-clock now.
    Without this, assets that were RECENT at snapshot time appear STALE when viewed later.

    Checks multiple sources in priority order:
    1. provenance.snapshot_generated_at (set during Farm run)
    2. generated_at (Farm adapter normalized field)
    3. created_at (raw Farm meta field)
    """
    if not run or not hasattr(run, 'input_meta') or not run.input_meta:
        return None

    provenance = run.input_meta.get("provenance", {})
    snapshot_generated_at = provenance.get("snapshot_generated_at") if provenance else None
    if snapshot_generated_at:
        if isinstance(snapshot_generated_at, datetime):
            return snapshot_generated_at
        if isinstance(snapshot_generated_at, str):
            return parse_iso_datetime(snapshot_generated_at)

    generated_at = run.input_meta.get("generated_at")
    if generated_at:
        if isinstance(generated_at, datetime):
            return generated_at
        if isinstance(generated_at, str):
            return parse_iso_datetime(generated_at)

    created_at = run.input_meta.get("created_at")
    if created_at:
        if isinstance(created_at, datetime):
            return created_at
        if isinstance(created_at, str):
            return parse_iso_datetime(created_at)

    return None


def generate_ambiguous_explanation(item: dict) -> str:
    """Generate plain English explanation for why a match is ambiguous."""
    entity_name = item.get("entity_name", "Unknown")
    plane = item.get("plane", "unknown")
    candidate_ids = item.get("candidate_ids", [])
    candidate_names = item.get("candidate_names", [])

    num_candidates = len(candidate_ids)

    plane_labels = {
        "idp": "identity provider",
        "cmdb": "CMDB",
        "cloud": "cloud inventory",
        "finance": "finance system",
        "discovery": "discovery"
    }
    plane_label = plane_labels.get(plane, plane)

    if plane == "finance":
        vendors = [n for n in candidate_names if not n.startswith("transaction_id=")]
        transactions = [n for n in candidate_names if n.startswith("transaction_id=")]

        parts = []
        if vendors:
            parts.append(f"{len(vendors)} vendor record{'s' if len(vendors) > 1 else ''}")
        if transactions:
            parts.append(f"{len(transactions)} transaction{'s' if len(transactions) > 1 else ''}")

        records_desc = " and ".join(parts) if parts else f"{num_candidates} records"

        return (
            f'"{entity_name}" matched {records_desc} in the {plane_label}. '
            f"This is ambiguous because multiple separate payment records could represent "
            f"the same vendor relationship, making it unclear which is authoritative."
        )

    elif plane == "idp":
        return (
            f'"{entity_name}" matched {num_candidates} identity records. '
            f"This is ambiguous because the application name appears in multiple SSO/SCIM entries, "
            f"possibly due to naming variations or duplicate app registrations."
        )

    elif plane == "cmdb":
        return (
            f'"{entity_name}" matched {num_candidates} CMDB configuration items. '
            f"This is ambiguous because multiple CI records exist with similar names, "
            f"possibly due to environment variants (dev/prod) or legacy entries."
        )

    elif plane == "cloud":
        return (
            f'"{entity_name}" matched {num_candidates} cloud resources. '
            f"This is ambiguous because multiple cloud assets share this name, "
            f"possibly across regions, accounts, or resource types."
        )

    else:
        return (
            f'"{entity_name}" matched {num_candidates} records in the {plane_label}. '
            f"This is ambiguous because multiple records could represent this asset."
        )
