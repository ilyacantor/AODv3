"""Admission gates - check criteria for each plane."""

from .idp import check_idp_admission, is_non_canonical_idp_app
from .cmdb import check_cmdb_admission
from .cloud import check_cloud_admission
from .finance import check_finance_admission, has_recurring_finance_spend
from .discovery import check_discovery_admission, build_discovery_footprint, DiscoveryFootprint

__all__ = [
    'check_idp_admission',
    'is_non_canonical_idp_app',
    'check_cmdb_admission',
    'check_cloud_admission',
    'check_finance_admission',
    'has_recurring_finance_spend',
    'check_discovery_admission',
    'build_discovery_footprint',
    'DiscoveryFootprint',
]
