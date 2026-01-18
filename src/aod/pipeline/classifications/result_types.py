"""Result types and dataclasses for derived classifications."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import ActivityStatus
from .time_utils import get_activity_status
from ...core.policy import get_current_config


@dataclass
class ClassificationResult:
    """Result of a derived classification check."""
    is_classified: bool
    is_indeterminate: bool
    classification_type: str
    reason: str
    evidence_summary: list[str]


@dataclass
class DistributionDiagnostic:
    """Diagnostic information about asset distribution."""
    total_assets: int = 0
    with_idp_match: int = 0
    with_cmdb_match: int = 0
    with_activity_last_30_days: int = 0
    with_any_activity_timestamp: int = 0
    indeterminate_count: int = 0


@dataclass
class DomainRollup:
    """
    Aggregated governance signals for a domain (OR logic across entities).

    When multiple assets share a domain, their governance signals are combined
    using OR logic: if ANY asset has IdP, the domain has IdP.
    """
    domain_key: str
    has_idp: bool
    has_cmdb: bool
    has_finance: bool
    has_cloud: bool
    has_discovery: bool
    latest_activity_at: Optional[datetime]
    entity_names: list[str]
    entity_count: int
    is_domain_canonical: bool = True
    alias_keys: list[str] = field(default_factory=list)
    has_ongoing_finance: bool = False  # Recurring spend (contracts/subscriptions)
    has_vendor_governed: bool = False  # Stage 3: Vendor governance propagation

    def get_activity_status(
        self,
        activity_window_days: Optional[int] = None,
        snapshot_as_of: Optional[datetime] = None
    ) -> ActivityStatus:
        """Get the activity status for this domain rollup."""
        if activity_window_days is None:
            activity_window_days = get_current_config().activity_windows.default_activity_window_days
        return get_activity_status(self.latest_activity_at, activity_window_days, snapshot_as_of)

    def is_anchored(self) -> bool:
        """
        Anchored predicate: asset is tracked/governed in at least one system.

        anchored = has_idp OR has_cmdb OR has_finance OR has_cloud

        Used to determine zombie eligibility - only anchored assets can be zombies
        because you can only deprovision what's tracked somewhere.
        """
        return self.has_idp or self.has_cmdb or self.has_finance or self.has_cloud

    def is_governed(self) -> bool:
        """
        Check if asset is governed (aligned with Policy Engine).

        Stage 3 Update: Governed = has_idp OR has_cmdb OR has_vendor_governed
        """
        return self.has_idp or self.has_cmdb or getattr(self, 'has_vendor_governed', False)

    def is_shadow(
        self,
        activity_window_days: Optional[int] = None,
        snapshot_as_of: Optional[datetime] = None
    ) -> bool:
        """
        Domain-level shadow: ungoverned AND activity_status==RECENT.

        Shadow = NOT is_governed AND activity_status==RECENT
        """
        if activity_window_days is None:
            activity_window_days = get_current_config().activity_windows.default_activity_window_days

        if not self.is_domain_canonical:
            return False

        if self.is_governed():
            return False

        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.RECENT

    def has_contact_point(self) -> bool:
        """
        Check if asset has a contact point for deprovisioning.

        Contact points include any means to identify who to reach out to.
        """
        return self.has_cmdb or self.has_idp or self.has_finance

    def is_zombie(
        self,
        activity_window_days: Optional[int] = None,
        snapshot_as_of: Optional[datetime] = None
    ) -> bool:
        """
        Domain-level zombie: governed AND stale AND ongoing finance.

        Zombie = is_governed AND activity_status==STALE AND has_ongoing_finance
        """
        if activity_window_days is None:
            activity_window_days = get_current_config().activity_windows.default_activity_window_days

        if not self.is_domain_canonical:
            return False

        if not self.is_governed():
            return False

        if not self.has_ongoing_finance:
            return False

        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.STALE

    def is_parked(
        self,
        activity_window_days: Optional[int] = None,
        snapshot_as_of: Optional[datetime] = None
    ) -> bool:
        """
        Domain-level parked: ungoverned AND stale.

        Parked = NOT is_governed AND activity_status==STALE
        """
        if activity_window_days is None:
            activity_window_days = get_current_config().activity_windows.default_activity_window_days

        if not self.is_domain_canonical:
            return False

        if self.is_governed():
            return False

        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.STALE

    def get_reason_codes(self) -> list[str]:
        """Generate canonical reason codes for this domain."""
        codes = []
        codes.append("HAS_IDP" if self.has_idp else "NO_IDP")
        codes.append("HAS_CMDB" if self.has_cmdb else "NO_CMDB")
        codes.append("HAS_FINANCE" if self.has_finance else "NO_FINANCE")
        codes.append("HAS_CLOUD" if self.has_cloud else "NO_CLOUD")
        codes.append("HAS_DISCOVERY" if self.has_discovery else "NO_DISCOVERY")

        activity_status = self.get_activity_status()
        if activity_status == ActivityStatus.RECENT:
            codes.append("RECENT_ACTIVITY")
        elif activity_status == ActivityStatus.STALE:
            codes.append("STALE_ACTIVITY")
        else:
            codes.append("NO_ACTIVITY_TIMESTAMPS")

        if self.is_anchored():
            codes.append("ANCHORED")
        else:
            codes.append("NOT_ANCHORED")

        if self.is_shadow():
            codes.append("SHADOW_CLASSIFICATION")
        elif self.is_zombie():
            codes.append("ZOMBIE_CLASSIFICATION")
        elif self.is_parked():
            codes.append("PARKED_CLASSIFICATION")

        return codes


@dataclass
class DerivedClassificationSummary:
    """Summary of derived classifications for a run."""
    shadow_count: int
    zombie_count: int
    parked_count: int
    indeterminate_count: int
    shadow_assets: list[dict]
    zombie_assets: list[dict]
    parked_assets: list[dict]
    distribution: DistributionDiagnostic = field(default_factory=DistributionDiagnostic)
    domain_rollups: dict[str, DomainRollup] = field(default_factory=dict)
