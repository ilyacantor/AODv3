"""
Normalize Farm snapshot data to canonical AOD schema.

This adapter transforms raw Farm JSON into the canonical Snapshot format
expected by AOD's Pydantic models. It handles field name variations,
missing optional fields, and structural differences.
"""

from datetime import datetime, timezone
from typing import Any
import hashlib


FIELD_ALIASES = {
    "observation": {
        "observation_id": ["id", "observationId", "observation_id"],
        "name": ["name", "observed_name", "observedName"],
        "domain": ["domain", "fqdn", "host"],
        "hostname": ["hostname", "host_name", "hostName"],
        "uri": ["uri", "url", "endpoint"],
        "vendor": ["vendor", "vendorName", "vendor_name"],
        "source": ["source", "dataSource", "data_source"],
        "observed_at": ["observed_at", "observedAt", "timestamp", "created_at"],
        "bytes_transferred": ["bytes_transferred", "bytesTransferred", "s_transferred"],
    },
    "meta": {
        "tenant_id": ["tenant_id", "tenantId"],
        "run_id": ["run_id", "runId"],
        "generated_at": ["generated_at", "generatedAt", "created_at", "createdAt"],
        "schema_version": ["schema_version", "schemaVersion", "version"],
        "profile": ["profile", "enterprise_profile"],
        "seed": ["seed"],
    },
    "idp_object": {
        "idp_id": ["idp_id", "idpId", "id"],
        "name": ["name", "displayName", "display_name"],
        "idp_type": ["idp_type", "idpType", "type"],
        "domain": ["domain"],
        "has_sso": ["has_sso", "hasSso", "ssoEnabled"],
        "has_scim": ["has_scim", "hasScim", "scimEnabled"],
        "owner": ["owner", "ownerEmail"],
    },
    "cmdb_ci": {
        "ci_id": ["ci_id", "ciId", "id", "sys_id"],
        "name": ["name", "displayName"],
        "ci_type": ["ci_type", "ciType", "type", "category"],
        "lifecycle": ["lifecycle", "lifecycleStatus", "lifecycle_status", "state"],
        "environment": ["environment", "env"],
        "owner": ["owner", "owned_by", "ownedBy"],
        "vendor": ["vendor", "manufacturer"],
    },
    "cloud_resource": {
        "resource_id": ["resource_id", "resourceId", "id", "arn"],
        "name": ["name", "resourceName"],
        "resource_type": ["resource_type", "resourceType", "type"],
        "provider": ["provider", "cloud_provider", "cloudProvider"],
        "uri": ["uri", "url", "endpoint"],
        "environment": ["environment", "env", "stage"],
    },
    "transaction": {
        "transaction_id": ["transaction_id", "transactionId", "id", "txn_id"],
        "vendor_id": ["vendor_id", "vendorId"],
        "vendor_name": ["vendor_name", "vendorName", "vendor"],
        "product": ["product", "productName", "description"],
        "memo": ["memo", "description", "notes"],
        "amount": ["amount", "value", "total"],
        "currency": ["currency", "currencyCode"],
        "date": ["date", "transaction_date", "transactionDate", "created_at"],
        "is_recurring": ["is_recurring", "isRecurring", "recurring"],
    },
}


class NormalizationError(Exception):
    """Raised when normalization cannot produce required canonical fields."""
    def __init__(self, message: str, missing_fields: list[str] | None = None):
        self.message = message
        self.missing_fields = missing_fields or []
        super().__init__(message)


def _get_aliased_value(data: dict, aliases: list[str], default: Any = None) -> Any:
    """Get value from dict using a list of possible field names."""
    for alias in aliases:
        if alias in data:
            return data[alias]
    return default


def _extract_raw_data(data: dict, known_fields: set[str]) -> dict | None:
    """Extract unknown fields into raw_data object."""
    raw = {k: v for k, v in data.items() if k not in known_fields}
    return raw if raw else None


def _generate_run_id(snapshot_id: str | None) -> str:
    """Generate deterministic run_id from snapshot_id."""
    if snapshot_id:
        return f"farm_{snapshot_id}"
    hash_input = str(datetime.now(timezone.utc).timestamp())
    return f"farm_{hashlib.sha256(hash_input.encode()).hexdigest()[:12]}"


def _normalize_datetime(value: Any) -> str | None:
    """Normalize datetime value to ISO format string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_observation(raw_obs: dict) -> dict:
    """Normalize a single observation to canonical format."""
    aliases = FIELD_ALIASES["observation"]
    
    obs_id = _get_aliased_value(raw_obs, aliases["observation_id"])
    if not obs_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Observation missing required identifier",
            missing_fields=["observation_id or id"]
        )
    
    name = _get_aliased_value(raw_obs, aliases["name"], obs_id)
    
    normalized = {
        "observation_id": str(obs_id),
        "name": str(name),
        "domain": _get_aliased_value(raw_obs, aliases["domain"]),
        "hostname": _get_aliased_value(raw_obs, aliases["hostname"]),
        "uri": _get_aliased_value(raw_obs, aliases["uri"]),
        "vendor": _get_aliased_value(raw_obs, aliases["vendor"]),
        "source": _get_aliased_value(raw_obs, aliases["source"], "discovery"),
    }
    
    observed_at = _get_aliased_value(raw_obs, aliases["observed_at"])
    if observed_at:
        normalized["observed_at"] = _normalize_datetime(observed_at)
    
    bytes_transferred = _get_aliased_value(raw_obs, aliases["bytes_transferred"])
    if bytes_transferred is not None:
        normalized["bytes_transferred"] = int(bytes_transferred)
    
    all_known = set()
    for alias_list in aliases.values():
        all_known.update(alias_list)
    raw_data = _extract_raw_data(raw_obs, all_known)
    if raw_data:
        normalized["raw_data"] = raw_data
    
    return normalized


def _normalize_idp_object(raw_obj: dict) -> dict:
    """Normalize a single IdP object to canonical format."""
    aliases = FIELD_ALIASES["idp_object"]
    
    idp_id = _get_aliased_value(raw_obj, aliases["idp_id"])
    if not idp_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: IdP object missing required identifier",
            missing_fields=["idp_id or id"]
        )
    
    name = _get_aliased_value(raw_obj, aliases["name"], str(idp_id))
    
    normalized = {
        "idp_id": str(idp_id),
        "name": str(name),
        "idp_type": _get_aliased_value(raw_obj, aliases["idp_type"], "app"),
        "domain": _get_aliased_value(raw_obj, aliases["domain"]),
        "has_sso": bool(_get_aliased_value(raw_obj, aliases["has_sso"], False)),
        "has_scim": bool(_get_aliased_value(raw_obj, aliases["has_scim"], False)),
        "owner": _get_aliased_value(raw_obj, aliases["owner"]),
    }
    
    all_known = set()
    for alias_list in aliases.values():
        all_known.update(alias_list)
    raw_data = _extract_raw_data(raw_obj, all_known)
    if raw_data:
        normalized["raw_data"] = raw_data
    
    return normalized


def _normalize_cmdb_ci(raw_ci: dict) -> dict:
    """Normalize a single CMDB CI to canonical format."""
    aliases = FIELD_ALIASES["cmdb_ci"]
    
    ci_id = _get_aliased_value(raw_ci, aliases["ci_id"])
    if not ci_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: CMDB CI missing required identifier",
            missing_fields=["ci_id or id"]
        )
    
    name = _get_aliased_value(raw_ci, aliases["name"], str(ci_id))
    
    normalized = {
        "ci_id": str(ci_id),
        "name": str(name),
        "ci_type": _get_aliased_value(raw_ci, aliases["ci_type"], "app"),
        "lifecycle": _get_aliased_value(raw_ci, aliases["lifecycle"], "unknown"),
        "environment": _get_aliased_value(raw_ci, aliases["environment"], "unknown"),
        "owner": _get_aliased_value(raw_ci, aliases["owner"]),
        "vendor": _get_aliased_value(raw_ci, aliases["vendor"]),
    }
    
    all_known = set()
    for alias_list in aliases.values():
        all_known.update(alias_list)
    raw_data = _extract_raw_data(raw_ci, all_known)
    if raw_data:
        normalized["raw_data"] = raw_data
    
    return normalized


def _normalize_cloud_resource(raw_res: dict) -> dict:
    """Normalize a single cloud resource to canonical format."""
    aliases = FIELD_ALIASES["cloud_resource"]
    
    res_id = _get_aliased_value(raw_res, aliases["resource_id"])
    if not res_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Cloud resource missing required identifier",
            missing_fields=["resource_id or id"]
        )
    
    name = _get_aliased_value(raw_res, aliases["name"], str(res_id))
    res_type = _get_aliased_value(raw_res, aliases["resource_type"])
    if not res_type:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Cloud resource missing required type",
            missing_fields=["resource_type or type"]
        )
    
    normalized = {
        "resource_id": str(res_id),
        "name": str(name),
        "resource_type": str(res_type),
        "provider": _get_aliased_value(raw_res, aliases["provider"], "aws"),
        "uri": _get_aliased_value(raw_res, aliases["uri"]),
        "environment": _get_aliased_value(raw_res, aliases["environment"], "unknown"),
    }
    
    all_known = set()
    for alias_list in aliases.values():
        all_known.update(alias_list)
    raw_data = _extract_raw_data(raw_res, all_known)
    if raw_data:
        normalized["raw_data"] = raw_data
    
    return normalized


def _normalize_transaction(raw_txn: dict) -> dict:
    """Normalize a single transaction to canonical format."""
    aliases = FIELD_ALIASES["transaction"]
    
    txn_id = _get_aliased_value(raw_txn, aliases["transaction_id"])
    if not txn_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Transaction missing required identifier",
            missing_fields=["transaction_id or id"]
        )
    
    normalized = {
        "transaction_id": str(txn_id),
        "vendor_id": _get_aliased_value(raw_txn, aliases["vendor_id"]),
        "vendor_name": _get_aliased_value(raw_txn, aliases["vendor_name"]),
        "product": _get_aliased_value(raw_txn, aliases["product"]),
        "memo": _get_aliased_value(raw_txn, aliases["memo"]),
        "amount": float(_get_aliased_value(raw_txn, aliases["amount"], 0)),
        "currency": _get_aliased_value(raw_txn, aliases["currency"], "USD"),
        "date": _normalize_datetime(_get_aliased_value(raw_txn, aliases["date"])),
        "is_recurring": bool(_get_aliased_value(raw_txn, aliases["is_recurring"], False)),
    }
    
    all_known = set()
    for alias_list in aliases.values():
        all_known.update(alias_list)
    raw_data = _extract_raw_data(raw_txn, all_known)
    if raw_data:
        normalized["raw_data"] = raw_data
    
    return normalized


def _find_observations(raw: dict) -> list[dict]:
    """Find observations list handling different nesting structures."""
    if "planes" in raw and isinstance(raw["planes"], dict):
        planes = raw["planes"]
        if "discovery" in planes and isinstance(planes["discovery"], dict):
            disc = planes["discovery"]
            if "observations" in disc:
                return disc["observations"] if isinstance(disc["observations"], list) else []
    
    if "discovery" in raw and isinstance(raw["discovery"], dict):
        disc = raw["discovery"]
        if "observations" in disc:
            return disc["observations"] if isinstance(disc["observations"], list) else []
    
    if "observations" in raw:
        return raw["observations"] if isinstance(raw["observations"], list) else []
    
    return []


def _find_plane_data(raw: dict, plane_name: str, list_key: str) -> list[dict]:
    """Find plane data handling different nesting structures."""
    if "planes" in raw and isinstance(raw["planes"], dict):
        planes = raw["planes"]
        if plane_name in planes and isinstance(planes[plane_name], dict):
            plane = planes[plane_name]
            if list_key in plane:
                return plane[list_key] if isinstance(plane[list_key], list) else []
    
    if plane_name in raw and isinstance(raw[plane_name], dict):
        plane = raw[plane_name]
        if list_key in plane:
            return plane[list_key] if isinstance(plane[list_key], list) else []
    
    return []


def normalize_farm_snapshot(raw: dict, fallback_tenant_id: str | None = None, snapshot_id: str | None = None) -> dict:
    """
    Normalize raw Farm snapshot data to canonical AOD schema.
    
    Args:
        raw: Raw snapshot JSON from Farm
        fallback_tenant_id: Tenant ID from request body (used if not in raw data)
        snapshot_id: Snapshot ID (used for generating run_id if missing)
        
    Returns:
        Normalized dict matching canonical Snapshot schema
        
    Raises:
        NormalizationError: If required fields cannot be derived
    """
    if not isinstance(raw, dict):
        raise NormalizationError(
            "INVALID_SNAPSHOT: Expected dict, got " + type(raw).__name__,
            missing_fields=["root object"]
        )
    
    raw_meta = raw.get("meta", {})
    if not isinstance(raw_meta, dict):
        raw_meta = {}
    
    meta_aliases = FIELD_ALIASES["meta"]
    
    tenant_id = _get_aliased_value(raw_meta, meta_aliases["tenant_id"])
    if not tenant_id:
        tenant_id = raw.get("tenant_id") or raw.get("tenantId") or fallback_tenant_id
    if not tenant_id:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Missing tenant_id in meta and no fallback provided",
            missing_fields=["meta.tenant_id", "tenant_id"]
        )
    
    run_id = _get_aliased_value(raw_meta, meta_aliases["run_id"])
    if not run_id:
        run_id = _generate_run_id(snapshot_id)
    
    generated_at = _get_aliased_value(raw_meta, meta_aliases["generated_at"])
    if not generated_at:
        generated_at = raw.get("created_at") or raw.get("createdAt")
    if not generated_at:
        generated_at = datetime.now(timezone.utc).isoformat()
    generated_at = _normalize_datetime(generated_at)
    
    schema_version = _get_aliased_value(raw_meta, meta_aliases["schema_version"])
    if not schema_version:
        schema_version = raw.get("schema_version") or raw.get("schemaVersion")
    if not schema_version:
        raise NormalizationError(
            "INVALID_SNAPSHOT: Missing schema_version - cannot determine data format",
            missing_fields=["meta.schema_version", "schema_version"]
        )
    
    normalized_meta = {
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "generated_at": generated_at,
        "schema_version": str(schema_version),
    }
    
    profile = _get_aliased_value(raw_meta, meta_aliases["profile"])
    if profile:
        normalized_meta["profile"] = str(profile)
    
    seed = _get_aliased_value(raw_meta, meta_aliases["seed"])
    if seed is not None:
        normalized_meta["seed"] = int(seed)
    
    raw_observations = _find_observations(raw)
    normalized_observations = []
    for i, obs in enumerate(raw_observations):
        if not isinstance(obs, dict):
            continue
        try:
            normalized_observations.append(_normalize_observation(obs))
        except NormalizationError as e:
            raise NormalizationError(
                f"INVALID_SNAPSHOT: Error in observation[{i}]: {e.message}",
                missing_fields=e.missing_fields
            )
    
    raw_idp_objects = _find_plane_data(raw, "idp", "objects")
    normalized_idp = []
    for obj in raw_idp_objects:
        if isinstance(obj, dict):
            try:
                normalized_idp.append(_normalize_idp_object(obj))
            except NormalizationError:
                pass
    
    raw_cmdb_cis = _find_plane_data(raw, "cmdb", "cis")
    normalized_cmdb = []
    for ci in raw_cmdb_cis:
        if isinstance(ci, dict):
            try:
                normalized_cmdb.append(_normalize_cmdb_ci(ci))
            except NormalizationError:
                pass
    
    raw_cloud = _find_plane_data(raw, "cloud", "resources")
    normalized_cloud = []
    for res in raw_cloud:
        if isinstance(res, dict):
            try:
                normalized_cloud.append(_normalize_cloud_resource(res))
            except NormalizationError:
                pass
    
    raw_transactions = _find_plane_data(raw, "finance", "transactions")
    normalized_transactions = []
    for txn in raw_transactions:
        if isinstance(txn, dict):
            try:
                normalized_transactions.append(_normalize_transaction(txn))
            except NormalizationError:
                pass
    
    raw_vendors = _find_plane_data(raw, "finance", "vendors")
    raw_contracts = _find_plane_data(raw, "finance", "contracts")
    
    raw_devices = _find_plane_data(raw, "endpoint", "devices")
    raw_installed_apps = _find_plane_data(raw, "endpoint", "installed_apps")
    
    raw_dns = _find_plane_data(raw, "network", "dns")
    raw_proxy = _find_plane_data(raw, "network", "proxy")
    raw_certs = _find_plane_data(raw, "network", "certs")
    
    normalized = {
        "meta": normalized_meta,
        "planes": {
            "discovery": {"observations": normalized_observations},
            "idp": {"objects": normalized_idp},
            "cmdb": {"cis": normalized_cmdb},
            "cloud": {"resources": normalized_cloud},
            "endpoint": {
                "devices": raw_devices,
                "installed_apps": raw_installed_apps,
            },
            "network": {
                "dns": raw_dns,
                "proxy": raw_proxy,
                "certs": raw_certs,
            },
            "finance": {
                "vendors": raw_vendors,
                "contracts": raw_contracts,
                "transactions": normalized_transactions,
            },
        },
    }
    
    return normalized
