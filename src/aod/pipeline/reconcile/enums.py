"""Enums for reconciliation module."""

from enum import Enum


class ReasonCode(str, Enum):
    """
    Reason codes explaining asset classification.

    These codes form a structured vocabulary for WHY assets get their
    shadow/zombie/active status. Each code represents a specific
    condition or evidence type.
    """
    # Governance signals
    HAS_IDP = "HAS_IDP"
    HAS_CMDB = "HAS_CMDB"
    NO_IDP = "NO_IDP"
    NO_CMDB = "NO_CMDB"

    # Activity signals
    RECENT_ACTIVITY = "RECENT_ACTIVITY"
    STALE_ACTIVITY = "STALE_ACTIVITY"
    NO_ACTIVITY_TIMESTAMPS = "NO_ACTIVITY_TIMESTAMPS"

    # Finance signals
    HAS_FINANCE = "HAS_FINANCE"
    NO_FINANCE = "NO_FINANCE"
    HAS_ONGOING_FINANCE = "HAS_ONGOING_FINANCE"

    # Cloud signals
    HAS_CLOUD = "HAS_CLOUD"
    NO_CLOUD = "NO_CLOUD"

    # Discovery signals
    HAS_DISCOVERY = "HAS_DISCOVERY"
    NO_DISCOVERY = "NO_DISCOVERY"

    # Classification outcomes
    SHADOW_CLASSIFICATION = "SHADOW_CLASSIFICATION"
    ZOMBIE_CLASSIFICATION = "ZOMBIE_CLASSIFICATION"
    PARKED_CLASSIFICATION = "PARKED_CLASSIFICATION"
    ACTIVE_CLASSIFICATION = "ACTIVE_CLASSIFICATION"

    # Eligibility/exclusion
    INFRASTRUCTURE_DOMAIN = "INFRASTRUCTURE_DOMAIN"
    INELIGIBLE_ASSET_TYPE = "INELIGIBLE_ASSET_TYPE"
    NOT_DOMAIN_CANONICAL = "NOT_DOMAIN_CANONICAL"

    # Stage 3: Vendor governance propagation
    HAS_VENDOR_GOVERNED = "HAS_VENDOR_GOVERNED"
    NO_VENDOR_GOVERNED = "NO_VENDOR_GOVERNED"


class AnchorType(str, Enum):
    """
    Types of anchoring for assets.

    An "anchored" asset is tracked in at least one authoritative system.
    This determines whether an asset can be a zombie candidate.
    """
    IDP = "idp"
    CMDB = "cmdb"
    FINANCE = "finance"
    CLOUD = "cloud"
    NONE = "none"
