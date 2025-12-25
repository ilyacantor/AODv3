"""Pydantic v2 models for AOD input contracts (Snapshot JSON)"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict

BANNED_FIELDS = frozenset([
    "is_shadow_it",
    "shadowScenario", 
    "shadowReasons",
    "shadow_scenario",
    "shadow_reasons",
    "inCMDB",
    "in_cmdb",
    "rulesTriggered",
    "rules_triggered",
    "conflictTypes",
    "conflict_types",
    "sourcePresence",
    "source_presence",
    "parked_reason",
    "ground_truth",
    "groundTruth",
])


def check_banned_fields(data: Any, path: str = "") -> list[str]:
    """Recursively check for banned fields anywhere in the data structure."""
    violations = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            if key.lower() in {f.lower() for f in BANNED_FIELDS} or key in BANNED_FIELDS:
                violations.append(current_path)
            violations.extend(check_banned_fields(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            violations.extend(check_banned_fields(item, f"{path}[{i}]"))
    
    return violations


class SnapshotMeta(BaseModel):
    """Metadata about the snapshot"""
    tenant_id: str
    run_id: str
    seed: Optional[int] = None
    generated_at: datetime
    profile: Optional[str] = None
    schema_version: Optional[str] = None


class Observation(BaseModel):
    """A discovery observation from the discovery plane"""
    observation_id: str
    name: Optional[str] = None
    domain: Optional[str] = None
    hostname: Optional[str] = None
    uri: Optional[str] = None
    vendor: Optional[str] = None
    source: str = "discovery"
    observed_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class DiscoveryPlane(BaseModel):
    """Discovery plane containing observations"""
    observations: list[Observation] = Field(default_factory=list)


class IdPObject(BaseModel):
    """Identity Provider object (user, group, service principal, app)"""
    idp_id: str
    name: str
    idp_type: str = "app"
    domain: Optional[str] = None
    has_sso: bool = False
    has_scim: bool = False
    owner: Optional[str] = None
    last_login_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class IdPPlane(BaseModel):
    """Identity Provider plane"""
    objects: list[IdPObject] = Field(default_factory=list)


class CMDBConfigItem(BaseModel):
    """CMDB Configuration Item"""
    ci_id: str
    name: str
    ci_type: str = "app"
    lifecycle: str = "unknown"
    environment: str = "unknown"
    owner: Optional[str] = None
    vendor: Optional[str] = None
    domain: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class CMDBPlane(BaseModel):
    """CMDB plane"""
    cis: list[CMDBConfigItem] = Field(default_factory=list)


class CloudResource(BaseModel):
    """Cloud resource"""
    resource_id: str
    name: str
    resource_type: str
    provider: str = "aws"
    uri: Optional[str] = None
    environment: str = "unknown"
    observed_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class CloudPlane(BaseModel):
    """Cloud plane"""
    resources: list[CloudResource] = Field(default_factory=list)


class EndpointDevice(BaseModel):
    """Endpoint device"""
    device_id: str
    hostname: str
    os: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class InstalledApp(BaseModel):
    """Installed application on endpoint"""
    app_id: str
    name: str
    device_id: str
    version: Optional[str] = None
    vendor: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class EndpointPlane(BaseModel):
    """Endpoint plane"""
    devices: list[EndpointDevice] = Field(default_factory=list)
    installed_apps: list[InstalledApp] = Field(default_factory=list)


class DNSRecord(BaseModel):
    """DNS record"""
    record_id: str
    domain: str
    record_type: str = "A"
    value: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class ProxyLog(BaseModel):
    """Proxy log entry"""
    log_id: str
    domain: str
    uri: Optional[str] = None
    user: Optional[str] = None
    bytes_transferred: int = 0
    timestamp: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class Certificate(BaseModel):
    """Certificate"""
    cert_id: str
    domain: str
    issuer: Optional[str] = None
    expires_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class NetworkPlane(BaseModel):
    """Network plane"""
    dns: list[DNSRecord] = Field(default_factory=list)
    proxy: list[ProxyLog] = Field(default_factory=list)
    certs: list[Certificate] = Field(default_factory=list)


class Vendor(BaseModel):
    """Vendor record"""
    vendor_id: str
    name: str
    products: list[str] = Field(default_factory=list)
    raw_data: Optional[dict[str, Any]] = None


class Contract(BaseModel):
    """Contract record"""
    contract_id: str
    vendor_id: Optional[str] = None  # Farm uses vendor_name instead
    vendor_name: Optional[str] = None
    product: Optional[str] = None
    amount: float = 0.0
    currency: str = "USD"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_recurring: bool = False
    raw_data: Optional[dict[str, Any]] = None


class Transaction(BaseModel):
    """Financial transaction"""
    transaction_id: str
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    product: Optional[str] = None
    memo: Optional[str] = None
    amount: float = 0.0
    currency: str = "USD"
    date: Optional[datetime] = None
    is_recurring: bool = False
    raw_data: Optional[dict[str, Any]] = None


class FinancePlane(BaseModel):
    """Finance plane"""
    vendors: list[Vendor] = Field(default_factory=list)
    contracts: list[Contract] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)


class Planes(BaseModel):
    """All evidence planes"""
    discovery: DiscoveryPlane = Field(default_factory=DiscoveryPlane)
    idp: IdPPlane = Field(default_factory=IdPPlane)
    cmdb: CMDBPlane = Field(default_factory=CMDBPlane)
    cloud: CloudPlane = Field(default_factory=CloudPlane)
    endpoint: EndpointPlane = Field(default_factory=EndpointPlane)
    network: NetworkPlane = Field(default_factory=NetworkPlane)
    finance: FinancePlane = Field(default_factory=FinancePlane)


class Snapshot(BaseModel):
    """Complete snapshot input contract"""
    meta: SnapshotMeta
    planes: Planes
    
    @model_validator(mode="before")
    @classmethod
    def reject_banned_fields(cls, data: Any) -> Any:
        """Reject any banned ground-truth fields anywhere in the payload"""
        if isinstance(data, dict):
            violations = check_banned_fields(data)
            if violations:
                raise ValueError(
                    f"INVALID_INPUT_CONTRACT: Banned ground-truth fields detected: {violations}. "
                    "AOD does not accept pre-adjudicated data."
                )
        return data
