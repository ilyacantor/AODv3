"""Stage 3: BuildPlaneIndexes - Build indexes for efficient correlation"""

import re
from dataclasses import dataclass, field

from ..models.input_contracts import (
    IdPPlane, CMDBPlane, CloudPlane, FinancePlane, Planes, PlaneRecord
)
from .normalize_observations import normalize_string, normalize_domain


@dataclass
class PlaneIndex:
    """Index for a single plane"""
    by_domain: dict[str, list[str]] = field(default_factory=dict)
    by_canonical_name: dict[str, list[str]] = field(default_factory=dict)
    by_uri: dict[str, list[str]] = field(default_factory=dict)
    by_vendor_product: dict[str, list[str]] = field(default_factory=dict)
    records: dict[str, PlaneRecord] = field(default_factory=dict)
    by_name_prefix: dict[str, list[str]] = field(default_factory=dict)
    by_name_bigrams: dict[str, list[str]] = field(default_factory=dict)
    by_name_words: dict[str, list[str]] = field(default_factory=dict)
    record_domains: dict[str, str] = field(default_factory=dict)
    record_domain_aliases: dict[str, set[str]] = field(default_factory=dict)


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


def add_to_domain_index(plane_index: 'PlaneIndex', domain_key: str, record_id: str):
    """Add a record ID to the domain index AND track the alias"""
    if not domain_key:
        return
    domain_key = domain_key.lower().strip()
    if domain_key not in plane_index.by_domain:
        plane_index.by_domain[domain_key] = []
    if record_id not in plane_index.by_domain[domain_key]:
        plane_index.by_domain[domain_key].append(record_id)
    if record_id not in plane_index.record_domain_aliases:
        plane_index.record_domain_aliases[record_id] = set()
    plane_index.record_domain_aliases[record_id].add(domain_key)


def generate_bigrams(text: str) -> set[str]:
    """Generate character bigrams from text"""
    text = text.lower().strip()
    if len(text) < 2:
        return set()
    return {text[i:i+2] for i in range(len(text) - 1)}


def extract_words(text: str) -> set[str]:
    """Extract words >= 4 chars for token matching"""
    words = re.split(r'[\s\-_./]+', text.lower().strip())
    return {w for w in words if len(w) >= 4}


def populate_fuzzy_indexes(index: PlaneIndex):
    """Pre-compute fuzzy matching indexes from canonical names"""
    for name, record_ids in index.by_canonical_name.items():
        if len(name) >= 4:
            prefix = name[:4]
            if prefix not in index.by_name_prefix:
                index.by_name_prefix[prefix] = []
            for rid in record_ids:
                if rid not in index.by_name_prefix[prefix]:
                    index.by_name_prefix[prefix].append(rid)
        
        for bigram in generate_bigrams(name):
            if bigram not in index.by_name_bigrams:
                index.by_name_bigrams[bigram] = []
            for rid in record_ids:
                if rid not in index.by_name_bigrams[bigram]:
                    index.by_name_bigrams[bigram].append(rid)
        
        for word in extract_words(name):
            if word not in index.by_name_words:
                index.by_name_words[word] = []
            for rid in record_ids:
                if rid not in index.by_name_words[word]:
                    index.by_name_words[word].append(rid)


def _get_raw_domain(domain: str) -> str:
    """Get cleaned raw domain without registered-domain extraction.
    
    This preserves tenant-specific subdomains like flowsoft.okta.com
    while still cleaning protocol/path/port.
    """
    if not domain:
        return ""
    cleaned = domain.lower().strip()
    cleaned = cleaned.removeprefix("http://")
    cleaned = cleaned.removeprefix("https://")
    cleaned = cleaned.split("/")[0]  # Remove path
    cleaned = cleaned.split(":")[0]  # Remove port
    cleaned = cleaned.removeprefix("www.")
    return cleaned


def _extract_tenant_token(domain: str) -> str:
    """Extract tenant token from subdomain-based tenant identifiers.
    
    Dec 2025 Fix: For domains like flowsoft.okta.com, extract 'flowsoft'
    as a searchable token. This enables cross-matching where:
    - Discovery has domain flowsoft.org → token 'flowsoft'
    - IdP has domain flowsoft.okta.com → tenant token 'flowsoft'
    
    Examples:
        flowsoft.okta.com → flowsoft
        acme-corp.servicenow.com → acmecorp
        company.salesforce.com → company
        simple.io → (empty, no subdomain)
    """
    if not domain:
        return ""
    
    raw = _get_raw_domain(domain)
    if not raw:
        return ""
    
    parts = raw.split(".")
    # Need at least 3 parts for subdomain.vendor.tld pattern
    if len(parts) < 3:
        return ""
    
    # First part is the tenant identifier
    tenant = parts[0]
    # Clean up: remove hyphens/underscores for matching
    tenant = tenant.replace("-", "").replace("_", "")
    
    # Only return if substantial (4+ chars)
    return tenant if len(tenant) >= 4 else ""


def _extract_domains_from_raw_data(raw_data: dict | None) -> list[str]:
    """Extract domain strings from raw_data fields.
    
    Dec 2025 Fix: Farm's IdP/CMDB payloads may contain domains in:
    - raw_data['domains'] (list of domains)
    - raw_data['urls'] (list of URLs)
    - raw_data['login_url'] (single login URL)
    - raw_data['domain'] (single domain string)
    """
    if not raw_data:
        return []
    
    domains = []
    
    if 'domain' in raw_data and raw_data['domain']:
        domains.append(str(raw_data['domain']))
    
    if 'domains' in raw_data and isinstance(raw_data['domains'], list):
        for d in raw_data['domains']:
            if d and isinstance(d, str):
                domains.append(d)
    
    if 'urls' in raw_data and isinstance(raw_data['urls'], list):
        for url in raw_data['urls']:
            if url and isinstance(url, str):
                cleaned = _get_raw_domain(url)
                if cleaned and '.' in cleaned:
                    domains.append(cleaned)
    
    if 'login_url' in raw_data and raw_data['login_url']:
        cleaned = _get_raw_domain(str(raw_data['login_url']))
        if cleaned and '.' in cleaned:
            domains.append(cleaned)
    
    return domains


def build_idp_index(idp_plane: IdPPlane) -> PlaneIndex:
    """Build IdP index: by domain, by canonical name, by vendor (if present).
    
    Dec 2025 Fix: Index BOTH registered domain AND raw domain to support:
    - Registered domain: vendor matching (okta.com, servicenow.com)
    - Raw domain: tenant-specific matching (flowsoft.okta.com)
    - Tenant token: cross-matching (flowsoft.okta.com → 'flowsoft' in by_name_words)
    - raw_data domains: domains from raw_data['domains'], raw_data['urls'], etc.
    """
    index = PlaneIndex()
    
    for obj in idp_plane.objects:
        record_id = obj.idp_id
        index.records[record_id] = obj
        
        canonical_name = normalize_string(obj.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        all_domain_sources = []
        
        if obj.domain:
            all_domain_sources.append(obj.domain)
        
        if '.' in record_id and '@' not in record_id:
            candidate = normalize_domain(record_id)
            if candidate and '.' in candidate:
                all_domain_sources.append(record_id)
        
        raw_data_domains = _extract_domains_from_raw_data(obj.raw_data)
        all_domain_sources.extend(raw_data_domains)
        
        for domain_source in all_domain_sources:
            registered = normalize_domain(domain_source)
            raw = _get_raw_domain(domain_source)
            
            add_to_domain_index(index, registered, record_id)
            if raw and raw != registered:
                add_to_domain_index(index, raw, record_id)
            
            if registered and record_id not in index.record_domains:
                index.record_domains[record_id] = registered
            
            tenant_token = _extract_tenant_token(domain_source)
            if tenant_token:
                add_to_index(index.by_name_words, tenant_token, record_id)
        
        vendor = getattr(obj, 'vendor', None) or (obj.raw_data.get('vendor') if obj.raw_data else None)
        if vendor:
            vendor_key = normalize_string(vendor)
            add_to_index(index.by_vendor_product, vendor_key, record_id)
    
    populate_fuzzy_indexes(index)
    return index


def build_cmdb_index(cmdb_plane: CMDBPlane) -> PlaneIndex:
    """Build CMDB index: by canonical name, by domain (external_ref), by vendor.
    
    Dec 2025 Fix: Index BOTH registered domain AND raw domain to support:
    - Registered domain: vendor matching
    - Raw domain: tenant-specific matching (company.servicenow.com)
    - Tenant token: cross-matching (company.servicenow.com → 'company' in by_name_words)
    - raw_data domains: domains from raw_data['domains'], raw_data['urls'], etc.
    """
    index = PlaneIndex()
    
    for ci in cmdb_plane.cis:
        record_id = ci.ci_id
        index.records[record_id] = ci
        
        canonical_name = normalize_string(ci.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        all_domain_sources = []
        
        if ci.domain:
            all_domain_sources.append(ci.domain)
        
        if '.' in record_id and '@' not in record_id:
            candidate = normalize_domain(record_id)
            if candidate and '.' in candidate:
                all_domain_sources.append(record_id)
        
        raw_data_domains = _extract_domains_from_raw_data(ci.raw_data)
        all_domain_sources.extend(raw_data_domains)
        
        for domain_source in all_domain_sources:
            registered = normalize_domain(domain_source)
            raw = _get_raw_domain(domain_source)
            
            add_to_domain_index(index, registered, record_id)
            if raw and raw != registered:
                add_to_domain_index(index, raw, record_id)
            
            if registered and record_id not in index.record_domains:
                index.record_domains[record_id] = registered
            
            tenant_token = _extract_tenant_token(domain_source)
            if tenant_token:
                add_to_index(index.by_name_words, tenant_token, record_id)
        
        if ci.vendor:
            vendor_key = normalize_string(ci.vendor)
            add_to_index(index.by_vendor_product, vendor_key, record_id)
    
    populate_fuzzy_indexes(index)
    return index


def build_cloud_index(cloud_plane: CloudPlane) -> PlaneIndex:
    """Build Cloud index: by uri/name"""
    index = PlaneIndex()
    
    for resource in cloud_plane.resources:
        record_id = resource.resource_id
        index.records[record_id] = resource
        
        canonical_name = normalize_string(resource.name)
        add_to_index(index.by_canonical_name, canonical_name, record_id)
        
        if resource.uri:
            uri = resource.uri.lower().strip()
            add_to_index(index.by_uri, uri, record_id)
    
    populate_fuzzy_indexes(index)
    return index


def build_finance_index(finance_plane: FinancePlane) -> PlaneIndex:
    """Build Finance index: by vendor+product and memo tokens"""
    index = PlaneIndex()
    
    # Build vendor lookup dict for O(1) access (optimization)
    vendor_by_id = {}
    for vendor in finance_plane.vendors:
        vendor_by_id[vendor.vendor_id] = vendor
        index.records[f"vendor:{vendor.vendor_id}"] = vendor

        vendor_name = normalize_string(vendor.name)
        add_to_index(index.by_vendor_product, vendor_name, f"vendor:{vendor.vendor_id}")
        add_to_index(index.by_canonical_name, vendor_name, f"vendor:{vendor.vendor_id}")

        for product in vendor.products:
            product_key = f"{vendor_name}:{normalize_string(product)}"
            add_to_index(index.by_vendor_product, product_key, f"vendor:{vendor.vendor_id}")
            add_to_index(index.by_canonical_name, normalize_string(product), f"vendor:{vendor.vendor_id}")

    for contract in finance_plane.contracts:
        record_id = f"contract:{contract.contract_id}"
        index.records[record_id] = contract

        # O(1) vendor lookup instead of O(n) loop
        vendor_record = vendor_by_id.get(contract.vendor_id)
        
        if vendor_record:
            vendor_name = normalize_string(vendor_record.name)
            add_to_index(index.by_vendor_product, vendor_name, record_id)
            add_to_index(index.by_canonical_name, vendor_name, record_id)
        
        if contract.vendor_name:
            vendor_name_from_contract = normalize_string(contract.vendor_name)
            add_to_index(index.by_canonical_name, vendor_name_from_contract, record_id)
            add_to_index(index.by_vendor_product, vendor_name_from_contract, record_id)
        
        if contract.product:
            product_name = normalize_string(contract.product)
            add_to_index(index.by_canonical_name, product_name, record_id)
            if vendor_record:
                product_key = f"{normalize_string(vendor_record.name)}:{product_name}"
                add_to_index(index.by_vendor_product, product_key, record_id)
    
    for txn in finance_plane.transactions:
        record_id = f"transaction:{txn.transaction_id}"
        index.records[record_id] = txn
        
        if txn.vendor_name:
            vendor_name = normalize_string(txn.vendor_name)
            add_to_index(index.by_vendor_product, vendor_name, record_id)
        
        if txn.product:
            product_name = normalize_string(txn.product)
            add_to_index(index.by_canonical_name, product_name, record_id)
        
        if txn.memo:
            tokens = normalize_string(txn.memo).split()
            for token in tokens:
                if len(token) > 3:
                    add_to_index(index.by_canonical_name, token, record_id)
    
    populate_fuzzy_indexes(index)
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
