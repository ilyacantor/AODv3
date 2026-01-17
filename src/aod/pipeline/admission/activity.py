"""Activity timestamp extraction from correlation evidence."""

from datetime import datetime, timezone
from typing import Optional

from ..correlate_entities import CorrelationResult, MatchStatus
from ..normalize_observations import CandidateEntity
from ..vendor_inference import extract_registered_domain
from ..domain_cache import extract_domain
from ...models.input_contracts import IdPObject, CloudResource, Transaction, Observation
from ...models.output_contracts import ActivityEvidence
from .constants import SOURCE_TO_PLANE, DISCOVERY_CORROBORATION_PLANES
from .idp_helpers import _extract_idp_domain, _idp_domain_matches_entity


def source_to_plane(source: str) -> Optional[str]:
    """Map a source to its parent plane."""
    return SOURCE_TO_PLANE.get(source.lower())


def extract_activity_timestamps(
    correlation: CorrelationResult,
    entity: CandidateEntity,
    observations: Optional[list[Observation]] = None,
    idp_activity_map: Optional[dict[str, datetime]] = None,
    propagated_idp: bool = False
) -> ActivityEvidence:
    """
    Extract activity timestamps from correlation evidence and observations.

    Cross-IdP activity aggregation: If the entity's matched IdP record has no
    last_login_at, we look up the IdP name in idp_activity_map to get the aggregated
    max login timestamp from ALL IdP records with the same name.

    Domain-scoped IdP activity: Only count IdP activity if the IdP record's domain
    matches the entity's primary registered domain. This prevents cross-domain IdP
    inheritance (e.g., easydesk.app IdP activity being counted for easydesk.dev
    entities) which causes false RECENT activity status.

    Args:
        correlation: Correlation result with matched records from various planes
        entity: The candidate entity being processed
        observations: Optional list of original observations for this entity
        idp_activity_map: Optional mapping of normalized IdP name -> max last_login_at
        propagated_idp: Whether IdP governance was propagated via vendor family

    Returns:
        ActivityEvidence with timestamps from each plane and computed latest_activity_at
    """
    timestamps: list[datetime] = []

    idp_last_login_at: Optional[datetime] = None
    discovery_observed_at: Optional[datetime] = None
    cloud_observed_at: Optional[datetime] = None
    endpoint_last_seen_at: Optional[datetime] = None
    network_last_seen_at: Optional[datetime] = None
    finance_last_transaction_at: Optional[datetime] = None
    idp_governance_aligned: bool = False  # Jan 2026: Track domain-aligned IdP separately from activity

    # Get entity's registered domains for IdP domain scoping
    entity_registered_domain = extract_registered_domain(entity.domain) if entity.domain else None
    entity_discovery_domains: set[str] = set()
    if entity_registered_domain:
        entity_discovery_domains.add(entity_registered_domain)

    # Include domains from non-IdP plane records (CMDB, Cloud, Finance, Discovery)
    for plane_match in [correlation.cmdb, correlation.cloud, correlation.finance]:
        if plane_match and plane_match.matched_records:
            for rec in plane_match.matched_records:
                if rec is None:
                    continue
                rec_domain = getattr(rec, 'domain', None) or getattr(rec, 'app_domain', None)
                if not rec_domain and hasattr(rec, 'raw_data') and isinstance(rec.raw_data, dict):
                    ext_ref = rec.raw_data.get('external_ref') or rec.raw_data.get('url')
                    if ext_ref and isinstance(ext_ref, str):
                        ext_result = extract_domain(ext_ref)
                        if ext_result.registered_domain:
                            rec_domain = ext_result.registered_domain
                if rec_domain:
                    reg = extract_registered_domain(rec_domain)
                    if reg:
                        entity_discovery_domains.add(reg)

    # Extract IdP activity and governance with TLD-aware domain matching
    if correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.idp.matched_records:
            if isinstance(record, IdPObject):
                # Check for non-canonical IdP name suffixes
                is_canonical_idp = True
                if record.name:
                    normalized_idp_name = record.name.lower()
                    for suffix in [' (legacy)', ' (deprecated)', '-legacy', '-prod', '-dev', '-staging',
                                   ' legacy', ' deprecated', ' production', '-production']:
                        if normalized_idp_name.endswith(suffix):
                            is_canonical_idp = False
                            break
                    if '(legacy)' in normalized_idp_name or '(deprecated)' in normalized_idp_name:
                        is_canonical_idp = False

                idp_registered_domain = _extract_idp_domain(record)

                # Use TLD-family matching for governance and activity
                domain_aligned = _idp_domain_matches_entity(
                    idp_registered_domain, entity_registered_domain, record.name
                )

                if domain_aligned:
                    # Exact or vendor-family domain match - provide governance and activity
                    idp_governance_aligned = True
                elif record.has_sso or record.has_scim:
                    # SSO/SCIM provides governance for cross-domain matches
                    idp_governance_aligned = True
                    if not is_canonical_idp:
                        # Non-canonical IdP - provides governance but skip activity inheritance
                        continue
                else:
                    # No domain match and no SSO/SCIM - skip entirely
                    continue

                login_ts = record.last_login_at
                # Fallback: Check raw_data for login timestamps if main field is empty
                if login_ts is None and record.raw_data and isinstance(record.raw_data, dict):
                    for field in ['last_login_at', 'lastLoginAt', 'lastLogin', 'last_activity', 'lastActivity']:
                        raw_val = record.raw_data.get(field)
                        if raw_val:
                            if isinstance(raw_val, datetime):
                                login_ts = raw_val
                                break
                            elif isinstance(raw_val, str):
                                try:
                                    parsed = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
                                    if parsed.tzinfo is None:
                                        parsed = parsed.replace(tzinfo=timezone.utc)
                                    login_ts = parsed
                                    break
                                except (ValueError, AttributeError):
                                    continue

                # Jan 2026: Cross-IdP activity aggregation
                if idp_activity_map and record.name:
                    normalized_name = record.name.lower().strip()
                    aggregated_ts = idp_activity_map.get(normalized_name)
                    if aggregated_ts:
                        if login_ts is None or aggregated_ts > login_ts:
                            login_ts = aggregated_ts

                if login_ts:
                    if idp_last_login_at is None or login_ts > idp_last_login_at:
                        idp_last_login_at = login_ts
        if idp_last_login_at:
            timestamps.append(idp_last_login_at)

    if observations:
        for obs in observations:
            if obs.observed_at and obs.source:
                source_lower = obs.source.lower()
                plane = source_to_plane(source_lower)
                # Only count observations from discovery-corroboration planes
                if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                    if discovery_observed_at is None or obs.observed_at > discovery_observed_at:
                        discovery_observed_at = obs.observed_at
        if discovery_observed_at:
            timestamps.append(discovery_observed_at)

    # Extract cloud timestamps
    if correlation.cloud.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource) and record.observed_at:
                if cloud_observed_at is None or record.observed_at > cloud_observed_at:
                    cloud_observed_at = record.observed_at
        if cloud_observed_at:
            timestamps.append(cloud_observed_at)

    # Finance timestamps - stored for metadata but NOT included in latest_activity_at
    # Per design: "Activity = Network Visibility OR Authentication Success"
    if correlation.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.finance.matched_records:
            if isinstance(record, Transaction) and record.date:
                if finance_last_transaction_at is None or record.date > finance_last_transaction_at:
                    finance_last_transaction_at = record.date
        # Do NOT add finance_last_transaction_at to timestamps!

    latest_activity_at = max(timestamps) if timestamps else None

    # Vendor-propagated IdP governance counts as domain-aligned
    if propagated_idp and not idp_governance_aligned:
        idp_governance_aligned = True

    return ActivityEvidence(
        idp_last_login_at=idp_last_login_at,
        discovery_observed_at=discovery_observed_at,
        cloud_observed_at=cloud_observed_at,
        endpoint_last_seen_at=endpoint_last_seen_at,
        network_last_seen_at=network_last_seen_at,
        finance_last_transaction_at=finance_last_transaction_at,
        latest_activity_at=latest_activity_at,
        idp_governance_aligned=idp_governance_aligned
    )
