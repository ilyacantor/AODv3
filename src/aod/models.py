from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class LifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PARKED = "PARKED"
    CATALOGED = "CATALOGED"


class FindingType(str, Enum):
    SHADOW_IT = "shadow_it"
    GOVERNANCE_GAP = "governance_gap"
    DATA_CONFLICTS = "data_conflicts"
    OPS_RISK = "ops_risk"
    LOW_CONFIDENCE = "low_confidence"


class Severity(str, Enum):
    CRITICAL = "critical"
    WARN = "warn"
    INFO = "info"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class Asset(BaseModel):
    id: str
    tenant_id: str
    farm_asset_id: str
    name: str
    asset_kind: str
    asset_type: Optional[str] = None
    vendor: Optional[str] = None
    environment: Optional[str] = None
    business_domain: Optional[str] = None
    tech_domain: Optional[str] = None
    system_role: Optional[str] = None
    owner: Optional[str] = None
    owner_email: Optional[str] = None
    owner_team: Optional[str] = None
    lifecycle_state: LifecycleState = LifecycleState.DISCOVERED
    parked_reason: Optional[str] = None
    is_shadow_it: bool = False
    has_data_conflicts: bool = False
    lens_coverage: Dict[str, bool] = {}
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Finding(BaseModel):
    id: str
    asset_id: str
    finding_type: FindingType
    rule_id: Optional[str] = None
    severity: Severity
    status: FindingStatus = FindingStatus.OPEN
    description: str
    evidence: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IngestRun(BaseModel):
    id: str
    tenant_id: str
    archetype: str
    scale: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_assets: int = 0
    shadow_it_count: int = 0
    parked_count: int = 0
    message: Optional[str] = None


class IngestRequest(BaseModel):
    archetype: str = "hybrid_sprawl"
    scale: str = "medium"
