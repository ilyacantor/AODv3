"""Result types and dataclasses for reconciliation module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from .enums import ReasonCode, AnchorType


@dataclass
class AssetActualResult:
    """
    Single asset reconciliation result.

    This is the actual outcome for one asset, including classification
    (shadow/zombie/active), reason codes, and supporting evidence.
    """
    # Core identity
    domain_key: str
    asset_names: list[str]
    asset_ids: list[str]

    # Classification
    classification: str  # "shadow", "zombie", "parked", "active"
    reason_codes: list[ReasonCode]

    # Governance evidence
    has_idp: bool = False
    has_cmdb: bool = False
    has_finance: bool = False
    has_cloud: bool = False
    has_discovery: bool = False
    has_ongoing_finance: bool = False
    has_vendor_governed: bool = False  # Stage 3: Vendor governance propagation

    # Activity evidence
    latest_activity_at: Optional[datetime] = None
    activity_status: str = "none"  # "recent", "stale", "none"

    # Metadata
    is_domain_canonical: bool = True
    anchor_types: list[AnchorType] = field(default_factory=list)
    entity_count: int = 1
    alias_domains: list[str] = field(default_factory=list)

    # Debug info
    match_debug: Optional[dict] = None

    def is_governed(self) -> bool:
        """Check if asset has authoritative governance."""
        return self.has_idp or self.has_cmdb or self.has_vendor_governed

    def is_anchored(self) -> bool:
        """Check if asset is tracked in any system."""
        return self.has_idp or self.has_cmdb or self.has_finance or self.has_cloud


@dataclass
class RejectionResult:
    """
    Rejection record for entities that didn't make it to assets.

    Tracks why an observed entity was rejected during admission.
    """
    entity_key: str
    entity_name: str
    reason_code: str
    reason_detail: str
    evidence_summary: dict = field(default_factory=dict)


@dataclass
class ActualResultsOutput:
    """
    Complete reconciliation output for a pipeline run.

    Contains all classified assets (shadow, zombie, parked, active),
    rejections, and summary statistics.
    """
    run_id: str
    tenant_id: str
    generated_at: datetime

    # Classified assets
    shadow_assets: list[AssetActualResult] = field(default_factory=list)
    zombie_assets: list[AssetActualResult] = field(default_factory=list)
    parked_assets: list[AssetActualResult] = field(default_factory=list)
    active_assets: list[AssetActualResult] = field(default_factory=list)

    # Rejections
    rejections: list[RejectionResult] = field(default_factory=list)

    # Summary stats
    total_entities_processed: int = 0
    total_assets_emitted: int = 0
    total_rejections: int = 0

    # Breakdown
    shadow_count: int = 0
    zombie_count: int = 0
    parked_count: int = 0
    active_count: int = 0

    # Configuration
    activity_window_days: int = 90

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "aod_discovery_id": self.run_id,
            "tenant_id": self.tenant_id,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_entities_processed": self.total_entities_processed,
                "total_assets_emitted": self.total_assets_emitted,
                "total_rejections": self.total_rejections,
                "shadow_count": self.shadow_count,
                "zombie_count": self.zombie_count,
                "parked_count": self.parked_count,
                "active_count": self.active_count,
                "activity_window_days": self.activity_window_days,
            },
            "shadow_assets": [_result_to_dict(a) for a in self.shadow_assets],
            "zombie_assets": [_result_to_dict(a) for a in self.zombie_assets],
            "parked_assets": [_result_to_dict(a) for a in self.parked_assets],
            "active_assets": [_result_to_dict(a) for a in self.active_assets],
            "rejections": [
                {
                    "entity_key": r.entity_key,
                    "entity_name": r.entity_name,
                    "reason_code": r.reason_code,
                    "reason_detail": r.reason_detail,
                    "evidence_summary": r.evidence_summary,
                }
                for r in self.rejections
            ],
        }


def _result_to_dict(result: AssetActualResult) -> dict:
    """Convert AssetActualResult to dictionary."""
    return {
        "domain_key": result.domain_key,
        "asset_names": result.asset_names,
        "asset_ids": result.asset_ids,
        "classification": result.classification,
        "reason_codes": [rc.value for rc in result.reason_codes],
        "governance": {
            "has_idp": result.has_idp,
            "has_cmdb": result.has_cmdb,
            "has_vendor_governed": result.has_vendor_governed,
            "is_governed": result.is_governed(),
        },
        "presence": {
            "has_finance": result.has_finance,
            "has_cloud": result.has_cloud,
            "has_discovery": result.has_discovery,
            "has_ongoing_finance": result.has_ongoing_finance,
            "is_anchored": result.is_anchored(),
        },
        "activity": {
            "latest_activity_at": result.latest_activity_at.isoformat() if result.latest_activity_at else None,
            "activity_status": result.activity_status,
        },
        "metadata": {
            "is_domain_canonical": result.is_domain_canonical,
            "anchor_types": [a.value for a in result.anchor_types],
            "entity_count": result.entity_count,
            "alias_domains": result.alias_domains,
        },
    }
