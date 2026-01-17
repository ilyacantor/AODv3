"""Result types for admission processing."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from ...models.output_contracts import Asset, ProvisioningStatus

if TYPE_CHECKING:
    from .gates.discovery import DiscoveryFootprint


@dataclass
class AdmissionResult:
    """
    Result of admission evaluation with Traffic Light status.

    Traffic Light System (fail-closed):
    - IGNORED: Hard rejection (invalid TLD, infrastructure domain) - dropped
    - ACTIVE: Trusted (has IdP or CMDB) - flows to DCL
    - REVIEW: Needs cleanup (CMDB but stale activity) - flagged for review
    - QUARANTINE: Shadow IT (Cloud/Finance/Discovery but no IdP/CMDB) - blocked from DCL
    """
    admitted: bool
    provisioning_status: ProvisioningStatus = ProvisioningStatus.QUARANTINE
    asset: Optional[Asset] = None
    rejection_reason: Optional[str] = None
    admission_reason: Optional[str] = None


class DiscoveryInvariantError(Exception):
    """Raised when discovery evidence invariants fail - indicates split-brain state."""
    pass


@dataclass
class DomainGateResult:
    """Result of domain gate checks (gates 0, 0.5, 1)."""
    passed: bool
    effective_domain: Optional[str] = None
    registered_domain: Optional[str] = None
    recovered_from_correlation: bool = False
    rejection: Optional[AdmissionResult] = None


@dataclass
class AdmissionEvidence:
    """Collected admission evidence from all planes."""
    idp_admitted: bool
    idp_reason: str
    cmdb_admitted: bool
    cmdb_reason: str
    cloud_admitted: bool
    cloud_reason: str
    finance_admitted: bool
    finance_reason: str
    discovery_admitted: bool
    discovery_reason: str
    footprint: 'DiscoveryFootprint'
    # Policy-adjusted values
    idp_can_admit: bool = False
    cmdb_can_admit: bool = False
    finance_can_admit: bool = False
