"""
Farm Snapshot Adapter - Contract-driven normalization from Farm wire format to AOD canonical schema.

This module contains the definitive mapping from Farm JSON to AOD's Pydantic models.
All field mappings are defined in FIELD_MAPPING tables - no ad-hoc transformations.

Validation flow: fetch raw -> normalize_farm_snapshot() -> Snapshot.model_validate()
"""

from datetime import datetime, timezone
from typing import Any
import hashlib

# =============================================================================
# FIELD MAPPING TABLES
# =============================================================================
# Format: canonical_field -> { sources: [farm_field, ...], default: value, transform: fn }

META_MAPPING = {
    "tenant_id": {"sources": ["tenant_id"], "required": True},
    "run_id": {"sources": ["run_id"], "default": None},  # synthesize if missing
    "generated_at": {"sources": ["created_at"], "required": True},
    "schema_version": {"sources": ["schema_version"], "required": True},
    "seed": {"sources": ["seed"], "default": None},
    "profile": {"sources": ["enterprise_profile", "profile"], "default": None},
}

OBSERVATION_MAPPING = {
    "observation_id": {"sources": ["observation_id"], "required": True},
    "name": {"sources": ["observed_name", "name"], "required": True},
    "domain": {"sources": ["domain"], "default": None},
    "hostname": {"sources": ["hostname"], "default": None},
    "uri": {"sources": ["observed_uri", "uri"], "default": None},
    "vendor": {"sources": ["vendor_hint", "vendor"], "default": None},
    "source": {"sources": ["source"], "default": "discovery"},
    "observed_at": {"sources": ["observed_at", "observedAt"], "default": None},
}

IDP_OBJECT_MAPPING = {
    "idp_id": {"sources": ["idp_id"], "required": True},
    "name": {"sources": ["name"], "required": True},
    "idp_type": {"sources": ["idp_type"], "default": "app"},
    "domain": {"sources": ["external_ref", "domain"], "default": None},
    "has_sso": {"sources": ["has_sso"], "default": False},
    "has_scim": {"sources": ["has_scim"], "default": False},
    "owner": {"sources": ["owner"], "default": None},
    "last_login_at": {"sources": ["last_login_at", "lastLoginAt"], "default": None},
}

CMDB_CI_MAPPING = {
    "ci_id": {"sources": ["ci_id"], "required": True},
    "name": {"sources": ["name"], "required": True},
    "ci_type": {"sources": ["ci_type"], "default": "app"},
    "lifecycle": {"sources": ["lifecycle"], "default": "unknown"},
    "environment": {"sources": ["environment"], "default": "unknown"},
    "owner": {"sources": ["owner", "owner_email"], "default": None},
    "vendor": {"sources": ["vendor"], "default": None},
}

CLOUD_RESOURCE_MAPPING = {
    "resource_id": {"sources": ["cloud_id", "resource_id"], "required": True},
    "name": {"sources": ["name"], "required": True},
    "resource_type": {"sources": ["resource_type"], "required": True},
    "provider": {"sources": ["cloud_provider", "provider"], "default": "aws"},
    "uri": {"sources": ["uri"], "default": None},
    "environment": {"sources": ["tags.environment", "environment"], "default": "unknown"},
    "observed_at": {"sources": ["observed_at", "observedAt"], "default": None},
}

ENDPOINT_DEVICE_MAPPING = {
    "device_id": {"sources": ["device_id"], "required": True},
    "hostname": {"sources": ["hostname"], "required": True},
    "os": {"sources": ["os"], "default": None},
}

INSTALLED_APP_MAPPING = {
    "app_id": {"sources": ["install_id", "app_id"], "required": True},
    "name": {"sources": ["app_name", "name"], "required": True},
    "device_id": {"sources": ["device_id"], "required": True},
    "version": {"sources": ["version"], "default": None},
    "vendor": {"sources": ["vendor"], "default": None},
    "last_seen_at": {"sources": ["last_seen_at", "lastSeenAt"], "default": None},
}

DNS_RECORD_MAPPING = {
    "record_id": {"sources": ["dns_id", "record_id"], "required": True},
    "domain": {"sources": ["queried_domain", "domain"], "required": True},
    "record_type": {"sources": ["record_type"], "default": "A"},
    "value": {"sources": ["value"], "default": None},
    "timestamp": {"sources": ["timestamp", "observed_at", "observedAt"], "default": None},
}

PROXY_LOG_MAPPING = {
    "log_id": {"sources": ["proxy_id", "log_id"], "required": True},
    "domain": {"sources": ["domain"], "required": True},
    "uri": {"sources": ["url", "uri"], "default": None},
    "user": {"sources": ["user_email", "user"], "default": None},
    "bytes_transferred": {"sources": ["bytes_transferred"], "default": 0},
    "timestamp": {"sources": ["timestamp", "observed_at", "observedAt"], "default": None},
}

CERTIFICATE_MAPPING = {
    "cert_id": {"sources": ["cert_id"], "required": True},
    "domain": {"sources": ["domain"], "required": True},
    "issuer": {"sources": ["issuer"], "default": None},
    "expires_at": {"sources": ["not_after", "expires_at"], "default": None},
}

VENDOR_MAPPING = {
    "vendor_id": {"sources": ["vendor_id"], "required": True},
    "name": {"sources": ["vendor_name", "name"], "required": True},
    "products": {"sources": ["products"], "default": []},
}

CONTRACT_MAPPING = {
    "contract_id": {"sources": ["contract_id"], "required": True},
    "vendor_id": {"sources": ["vendor_id"], "default": None},
    "vendor_name": {"sources": ["vendor_name"], "default": None},
    "product": {"sources": ["product"], "default": None},
    "amount": {"sources": ["amount"], "default": 0.0},
    "currency": {"sources": ["currency"], "default": "USD"},
    "start_date": {"sources": ["start_date"], "default": None},
    "end_date": {"sources": ["end_date"], "default": None},
}

TRANSACTION_MAPPING = {
    "transaction_id": {"sources": ["txn_id", "transaction_id"], "required": True},
    "vendor_id": {"sources": ["vendor_id"], "default": None},
    "vendor_name": {"sources": ["vendor_name"], "default": None},
    "product": {"sources": ["product"], "default": None},
    "memo": {"sources": ["memo"], "default": None},
    "amount": {"sources": ["amount"], "default": 0.0},
    "currency": {"sources": ["currency"], "default": "USD"},
    "date": {"sources": ["date", "datetime", "timestamp"], "default": None},
    "is_recurring": {"sources": ["is_recurring"], "default": False},
}


# =============================================================================
# NORMALIZATION ERROR
# =============================================================================

class NormalizationError(Exception):
    """Raised when normalization cannot produce required canonical fields."""
    def __init__(self, message: str, missing_fields: list[str] | None = None):
        self.message = message
        self.missing_fields = missing_fields or []
        super().__init__(message)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_value(data: dict, sources: list[str], default: Any = None) -> Any:
    """Get value from dict using list of possible source paths."""
    for source in sources:
        if "." in source:
            parts = source.split(".")
            val = data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    val = None
                    break
            if val is not None:
                return val
        elif source in data:
            return data[source]
    return default


def _normalize_datetime(value: Any) -> str | None:
    """Normalize datetime to ISO format string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _generate_run_id(snapshot_id: str | None) -> str:
    """Generate deterministic run_id from snapshot_id."""
    if snapshot_id:
        return f"farm_{snapshot_id}"
    return f"farm_{hashlib.sha256(str(datetime.now(timezone.utc).timestamp()).encode()).hexdigest()[:12]}"


def _extract_raw_data(data: dict, mapped_keys: set[str]) -> dict | None:
    """Extract unmapped fields into raw_data."""
    raw = {k: v for k, v in data.items() if k not in mapped_keys}
    return raw if raw else None


def _apply_mapping(data: dict, mapping: dict[str, dict], record_type: str) -> dict:
    """Apply a mapping table to transform a record."""
    result = {}
    mapped_keys = set()
    
    for canonical_field, spec in mapping.items():
        sources = spec["sources"]
        default = spec.get("default")
        required = spec.get("required", False)
        
        value = _get_value(data, sources, default)
        mapped_keys.update(sources)
        
        if required and value is None:
            raise NormalizationError(
                f"INVALID_SNAPSHOT: {record_type} missing required field",
                missing_fields=[f"{canonical_field} (expected from: {sources})"]
            )
        
        if value is not None or not required:
            result[canonical_field] = value
    
    raw_data = _extract_raw_data(data, mapped_keys)
    if raw_data:
        result["raw_data"] = raw_data
    
    return result


# =============================================================================
# PLANE NORMALIZERS
# =============================================================================

def _normalize_meta(raw_meta: dict, fallback_tenant_id: str | None, snapshot_id: str | None) -> dict:
    """Normalize meta section."""
    result = {}
    
    tenant_id = _get_value(raw_meta, META_MAPPING["tenant_id"]["sources"])
    if not tenant_id:
        tenant_id = fallback_tenant_id
    if not tenant_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Missing tenant_id",
            missing_fields=["meta.tenant_id"]
        )
    result["tenant_id"] = str(tenant_id)
    
    run_id = _get_value(raw_meta, META_MAPPING["run_id"]["sources"])
    if not run_id:
        run_id = _generate_run_id(snapshot_id or raw_meta.get("snapshot_id"))
    result["run_id"] = str(run_id)
    
    generated_at = _get_value(raw_meta, META_MAPPING["generated_at"]["sources"])
    if not generated_at:
        generated_at = datetime.now(timezone.utc).isoformat()
    result["generated_at"] = _normalize_datetime(generated_at)
    
    schema_version = _get_value(raw_meta, META_MAPPING["schema_version"]["sources"])
    if not schema_version:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Missing schema_version",
            missing_fields=["meta.schema_version"]
        )
    result["schema_version"] = str(schema_version)
    
    seed = _get_value(raw_meta, META_MAPPING["seed"]["sources"])
    if seed is not None:
        result["seed"] = int(seed)
    
    profile = _get_value(raw_meta, META_MAPPING["profile"]["sources"])
    if profile:
        result["profile"] = str(profile)
    
    return result


def _normalize_observations(raw_list: list) -> list[dict]:
    """Normalize discovery observations."""
    result = []
    for i, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            continue
        try:
            normalized = _apply_mapping(raw, OBSERVATION_MAPPING, f"Observation[{i}]")
            result.append(normalized)
        except NormalizationError:
            pass  # Skip invalid records
    return result


def _normalize_idp_objects(raw_list: list) -> list[dict]:
    """Normalize IdP objects."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, IDP_OBJECT_MAPPING, "IdPObject"))
        except NormalizationError:
            pass
    return result


def _normalize_cmdb_cis(raw_list: list) -> list[dict]:
    """Normalize CMDB CIs."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, CMDB_CI_MAPPING, "CMDBConfigItem"))
        except NormalizationError:
            pass
    return result


def _normalize_cloud_resources(raw_list: list) -> list[dict]:
    """Normalize cloud resources."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            normalized = _apply_mapping(raw, CLOUD_RESOURCE_MAPPING, "CloudResource")
            if normalized.get("environment") == "unknown" and isinstance(raw.get("tags"), dict):
                env = raw["tags"].get("environment")
                if env:
                    normalized["environment"] = env
            result.append(normalized)
        except NormalizationError:
            pass
    return result


def _normalize_devices(raw_list: list) -> list[dict]:
    """Normalize endpoint devices."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, ENDPOINT_DEVICE_MAPPING, "EndpointDevice"))
        except NormalizationError:
            pass
    return result


def _normalize_installed_apps(raw_list: list) -> list[dict]:
    """Normalize installed apps."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, INSTALLED_APP_MAPPING, "InstalledApp"))
        except NormalizationError:
            pass
    return result


def _normalize_dns_records(raw_list: list) -> list[dict]:
    """Normalize DNS records."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, DNS_RECORD_MAPPING, "DNSRecord"))
        except NormalizationError:
            pass
    return result


def _normalize_proxy_logs(raw_list: list) -> list[dict]:
    """Normalize proxy logs."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, PROXY_LOG_MAPPING, "ProxyLog"))
        except NormalizationError:
            pass
    return result


def _normalize_certificates(raw_list: list) -> list[dict]:
    """Normalize certificates."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, CERTIFICATE_MAPPING, "Certificate"))
        except NormalizationError:
            pass
    return result


def _normalize_vendors(raw_list: list) -> list[dict]:
    """Normalize vendors."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, VENDOR_MAPPING, "Vendor"))
        except NormalizationError:
            pass
    return result


def _normalize_contracts(raw_list: list) -> list[dict]:
    """Normalize contracts."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, CONTRACT_MAPPING, "Contract"))
        except NormalizationError:
            pass
    return result


def _normalize_transactions(raw_list: list) -> list[dict]:
    """Normalize transactions."""
    result = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_apply_mapping(raw, TRANSACTION_MAPPING, "Transaction"))
        except NormalizationError:
            pass
    return result


# =============================================================================
# MAIN NORMALIZATION FUNCTION
# =============================================================================

def normalize_farm_snapshot(
    raw: dict,
    fallback_tenant_id: str | None = None,
    snapshot_id: str | None = None
) -> dict:
    """
    Normalize raw Farm snapshot to canonical AOD schema.
    
    Args:
        raw: Raw Farm snapshot JSON
        fallback_tenant_id: Tenant ID from request (if not in payload)
        snapshot_id: Snapshot ID for run_id generation
        
    Returns:
        Normalized dict matching canonical Snapshot schema
        
    Raises:
        NormalizationError: If required fields cannot be derived
    """
    if not isinstance(raw, dict):
        raise NormalizationError(
            f"INVALID_SNAPSHOT: Expected dict, got {type(raw).__name__}",
            missing_fields=["root object"]
        )
    
    raw_meta = raw.get("meta", {})
    if not isinstance(raw_meta, dict):
        raw_meta = {}
    
    normalized_meta = _normalize_meta(raw_meta, fallback_tenant_id, snapshot_id)
    
    planes = raw.get("planes", {})
    if not isinstance(planes, dict):
        planes = {}
    
    discovery = planes.get("discovery", {})
    idp = planes.get("idp", {})
    cmdb = planes.get("cmdb", {})
    cloud = planes.get("cloud", {})
    endpoint = planes.get("endpoint", {})
    network = planes.get("network", {})
    finance = planes.get("finance", {})
    
    return {
        "meta": normalized_meta,
        "planes": {
            "discovery": {
                "observations": _normalize_observations(discovery.get("observations", []))
            },
            "idp": {
                "objects": _normalize_idp_objects(idp.get("objects", []))
            },
            "cmdb": {
                "cis": _normalize_cmdb_cis(cmdb.get("cis", []))
            },
            "cloud": {
                "resources": _normalize_cloud_resources(cloud.get("resources", []))
            },
            "endpoint": {
                "devices": _normalize_devices(endpoint.get("devices", [])),
                "installed_apps": _normalize_installed_apps(endpoint.get("installed_apps", []))
            },
            "network": {
                "dns": _normalize_dns_records(network.get("dns", [])),
                "proxy": _normalize_proxy_logs(network.get("proxy", [])),
                "certs": _normalize_certificates(network.get("certs", []))
            },
            "finance": {
                "vendors": _normalize_vendors(finance.get("vendors", [])),
                "contracts": _normalize_contracts(finance.get("contracts", [])),
                "transactions": _normalize_transactions(finance.get("transactions", []))
            }
        }
    }
