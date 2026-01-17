"""Helper functions for extracting data from plane records."""

import re
from typing import Optional, Any

from .constants import ENV_SUFFIXES, LEGACY_MARKERS
from ..normalize_observations import normalize_string
from ...models.input_contracts import PlaneRecord


def extract_base_name(name: str) -> str:
    """Extract base name by stripping environment suffixes and legacy markers."""
    normalized = normalize_string(name)

    for suffix in ENV_SUFFIXES | LEGACY_MARKERS:
        patterns = [
            rf"[-_]?{suffix}[-_]?$",
            rf"^{suffix}[-_]",
            rf"[-_]{suffix}[-_]",
        ]
        for pattern in patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

    return normalized.strip("-_")


def is_legacy_name(name: str) -> bool:
    """Check if a name contains legacy/deprecated markers."""
    normalized = name.lower()
    return any(marker in normalized for marker in LEGACY_MARKERS)


def get_record_name(record: PlaneRecord) -> str:
    """Extract name from a record (handles dict or object).

    Also checks vendor_name for finance Transaction records.
    """
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("name", "") or record.get("app_name", "") or record.get("vendor_name", "") or ""
    return getattr(record, "name", "") or getattr(record, "app_name", "") or getattr(record, "vendor_name", "") or ""


def get_record_vendor(record: PlaneRecord) -> str:
    """Extract vendor from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("vendor", "") or ""
    return getattr(record, "vendor", "") or ""


def extract_domain_base_token(domain: str) -> str:
    """Extract base token from domain (e.g., 'pagerduty.com' -> 'pagerduty', 'service-now.com' -> 'servicenow')."""
    if not domain:
        return ""
    normalized = domain.lower().strip()
    normalized = normalized.removeprefix("www.")
    parts = normalized.split(".")
    if parts:
        token = parts[0]
        token = token.replace("-", "").replace("_", "")
        return token
    return ""


def get_record_field(record: PlaneRecord, field: str, default=None) -> Any:
    """Extract a field from a record (handles dict or object)."""
    if record is None:
        return default
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def is_deprecated_by_field(record: PlaneRecord) -> bool:
    """Check if a record is deprecated based on actual CMDB fields."""
    status = str(get_record_field(record, "status", "") or "").lower()
    lifecycle = str(get_record_field(record, "lifecycle_state", "") or "").lower()
    is_deprecated = get_record_field(record, "is_deprecated", False)
    is_retired = get_record_field(record, "is_retired", False)

    deprecated_statuses = {"deprecated", "retired", "archived", "decommissioned", "obsolete", "inactive"}

    if is_deprecated or is_retired:
        return True
    if status in deprecated_statuses:
        return True
    if lifecycle in deprecated_statuses:
        return True

    return False


def get_environment_field(record: PlaneRecord) -> Optional[str]:
    """Extract environment from actual CMDB field."""
    env = get_record_field(record, "environment")
    if env:
        return str(env).lower()

    env_type = get_record_field(record, "environment_type")
    if env_type:
        return str(env_type).lower()

    return None


# Aliases with underscore prefix for backwards compatibility
_extract_base_name = extract_base_name
_is_legacy_name = is_legacy_name
_get_record_name = get_record_name
_get_record_vendor = get_record_vendor
_extract_domain_base_token = extract_domain_base_token
_get_record_field = get_record_field
_is_deprecated_by_field = is_deprecated_by_field
_get_environment_field = get_environment_field
