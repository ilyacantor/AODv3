"""Stage 3: BuildPlaneIndexes - Build indexes for efficient correlation"""

from dataclasses import dataclass, field
from typing import Any

from ..models.input_contracts import (
    IdPPlane, CMDBPlane, CloudPlane, FinancePlane, Planes
)
from .normalize_observations import normalize_string
from .domain_normalization import derive_canonical_asset_key, looks_like_domain
from .aod_agent_reconcile import VENDOR_TO_DOMAIN


@dataclass
class PlaneIndex:
    """Index for a single plane"""
    by_domain: dict[str, list[str]] = field(default_factory=dict)
    by_canonical_name: dict[str, list[str]] = field(default_factory=dict)
    by_uri: dict[str, list[str]] = field(default_factory=dict)
    by_vendor_product: dict[str, list[str]] = field(default_factory=dict)
    records: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlaneIndexes:
    """All plane indexes"""
    idp: PlaneIndex = field(default_factory=PlaneIndex)
    cmdb: PlaneIndex = field(default_factory=PlaneIndex)
    cloud: PlaneIndex = field(default_factory=PlaneIndex)
    finance: PlaneIndex = field(default_factory=PlaneIndex)


def add_to_index(index: dict[str, list[str]], key: str, record_id: str):
    """Add a record ID to an index under a key"""
    if not key:
        return
    key = key.lower().strip()
    if key not in index:
        index[key] = []
    if record_id not in index[key]:
        index[key].append(record_id)


def build_idp_index(idp_plane: IdPPlane) -> PlaneIndex:
    """Build IdP index: by domain (canonical eTLD+1), by canonical name, by vendor"""
    index = PlaneIndex()
    
    for obj in idp_plane.objects:
        record_id = obj.idp_id
        index.records[record_id] = obj
        
        canonical_name = normalize_string(obj.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        if obj.domain:
            domain = derive_canonical_asset_key(obj.domain)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if looks_like_domain(obj.name):
            domain = derive_canonical_asset_key(obj.name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        vendor = getattr(obj, 'vendor', None) or (obj.raw_data.get('vendor') if obj.raw_data else None)
        if vendor:
            vendor_key = normalize_string(vendor)
            add_to_index(index.by_vendor_product, vendor_key, record_id)
    
    return index


def build_cmdb_index(cmdb_plane: CMDBPlane) -> PlaneIndex:
    """Build CMDB index: by canonical name, by domain (canonical eTLD+1), by vendor"""
    index = PlaneIndex()
    
    for ci in cmdb_plane.cis:
        record_id = ci.ci_id
        index.records[record_id] = ci
        
        canonical_name = normalize_string(ci.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        if ci.domain:
            domain = derive_canonical_asset_key(ci.domain)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if looks_like_domain(ci.name):
            domain = derive_canonical_asset_key(ci.name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if ci.raw_data and isinstance(ci.raw_data, dict):
            for field_name in ['external_ref', 'url', 'endpoint', 'homepage']:
                url = ci.raw_data.get(field_name)
                if url:
                    domain = derive_canonical_asset_key(url)
                    if domain:
                        add_to_index(index.by_domain, domain, record_id)
        
        if ci.vendor:
            vendor_key = normalize_string(ci.vendor)
            add_to_index(index.by_vendor_product, vendor_key, record_id)
    
    return index


def build_cloud_index(cloud_plane: CloudPlane) -> PlaneIndex:
    """Build Cloud index: by uri/name with canonical domain extraction"""
    index = PlaneIndex()
    
    for resource in cloud_plane.resources:
        record_id = resource.resource_id
        index.records[record_id] = resource
        
        canonical_name = normalize_string(resource.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        if resource.uri:
            uri = resource.uri.lower().strip()
            add_to_index(index.by_uri, uri, record_id)
            
            domain = derive_canonical_asset_key(resource.uri)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if looks_like_domain(resource.name):
            domain = derive_canonical_asset_key(resource.name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
    
    return index


def _extract_domain_from_vendor(vendor_name: str) -> str | None:
    """
    Extract canonical domain from vendor name using VENDOR_TO_DOMAIN lookup.
    
    This enables domain-first finance linking:
    1. Vendor name -> domain lookup
    2. Vendor name looks like domain -> eTLD+1
    """
    if not vendor_name:
        return None
    
    vendor_key = vendor_name.lower().strip()
    if vendor_key in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[vendor_key]
    
    if looks_like_domain(vendor_key):
        return derive_canonical_asset_key(vendor_key)
    
    return None


def build_finance_index(finance_plane: FinancePlane) -> PlaneIndex:
    """
    Build Finance index: by domain, vendor+product, and memo tokens.
    
    DOMAIN-FIRST LINKING (Patch 2 compliance):
    - Extract domains from vendor names via VENDOR_TO_DOMAIN lookup
    - Extract domains from vendor names that look like domains
    - Extract domains from raw_data fields (url, domain, website)
    
    This ensures finance evidence links to assets by domain when possible.
    """
    index = PlaneIndex()
    
    for vendor in finance_plane.vendors:
        record_id = f"vendor:{vendor.vendor_id}"
        index.records[record_id] = vendor
        
        vendor_name = normalize_string(vendor.name)
        add_to_index(index.by_vendor_product, vendor_name, record_id)
        add_to_index(index.by_canonical_name, vendor_name, record_id)
        
        domain = _extract_domain_from_vendor(vendor.name)
        if domain:
            add_to_index(index.by_domain, domain, record_id)
        
        for product in vendor.products:
            product_key = f"{vendor_name}:{normalize_string(product)}"
            add_to_index(index.by_vendor_product, product_key, record_id)
            add_to_index(index.by_canonical_name, normalize_string(product), record_id)
            
            product_domain = _extract_domain_from_vendor(product)
            if product_domain:
                add_to_index(index.by_domain, product_domain, record_id)
    
    for contract in finance_plane.contracts:
        record_id = f"contract:{contract.contract_id}"
        index.records[record_id] = contract
        
        vendor_record = None
        for v in finance_plane.vendors:
            if v.vendor_id == contract.vendor_id:
                vendor_record = v
                break
        
        if vendor_record:
            vendor_name = normalize_string(vendor_record.name)
            add_to_index(index.by_vendor_product, vendor_name, record_id)
            add_to_index(index.by_canonical_name, vendor_name, record_id)
            
            domain = _extract_domain_from_vendor(vendor_record.name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if contract.vendor_name:
            vendor_name_from_contract = normalize_string(contract.vendor_name)
            add_to_index(index.by_canonical_name, vendor_name_from_contract, record_id)
            add_to_index(index.by_vendor_product, vendor_name_from_contract, record_id)
            
            domain = _extract_domain_from_vendor(contract.vendor_name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if contract.product:
            product_name = normalize_string(contract.product)
            add_to_index(index.by_canonical_name, product_name, record_id)
            if vendor_record:
                product_key = f"{normalize_string(vendor_record.name)}:{product_name}"
                add_to_index(index.by_vendor_product, product_key, record_id)
        
        if contract.raw_data and isinstance(contract.raw_data, dict):
            for field_name in ['url', 'domain', 'website', 'vendor_url']:
                url = contract.raw_data.get(field_name)
                if url:
                    domain = derive_canonical_asset_key(url)
                    if domain:
                        add_to_index(index.by_domain, domain, record_id)
    
    for txn in finance_plane.transactions:
        record_id = f"transaction:{txn.transaction_id}"
        index.records[record_id] = txn
        
        if txn.vendor_name:
            vendor_name = normalize_string(txn.vendor_name)
            add_to_index(index.by_vendor_product, vendor_name, record_id)
            
            domain = _extract_domain_from_vendor(txn.vendor_name)
            if domain:
                add_to_index(index.by_domain, domain, record_id)
        
        if txn.product:
            product_name = normalize_string(txn.product)
            add_to_index(index.by_canonical_name, product_name, record_id)
        
        if txn.memo:
            tokens = normalize_string(txn.memo).split()
            for token in tokens:
                if len(token) > 3:
                    add_to_index(index.by_canonical_name, token, record_id)
    
    return index


def build_plane_indexes(planes: Planes) -> PlaneIndexes:
    """
    Build indexes for all planes for efficient correlation.
    
    Args:
        planes: All evidence planes from snapshot
        
    Returns:
        PlaneIndexes containing indexed data for each plane
    """
    return PlaneIndexes(
        idp=build_idp_index(planes.idp),
        cmdb=build_cmdb_index(planes.cmdb),
        cloud=build_cloud_index(planes.cloud),
        finance=build_finance_index(planes.finance)
    )
