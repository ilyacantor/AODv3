"""Asset building and admission criteria application."""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..correlate_entities import CorrelationResult, MatchStatus
from ..normalize_observations import CandidateEntity
from ..deterministic_ids import deterministic_uuid
from ..vendor_inference import extract_registered_domain
from ..domain_cache import extract_domain
from ...models.input_contracts import Observation
from ...models.output_contracts import (
    Asset, AssetType, Environment, LensStatus, LensStatuses, LensCoverage, AssetIdentifiers,
    ProvisioningStatus, VendorHypothesis
)

from .constants import PROMOTION_ALLOWED_MATCH_METHODS, PROMOTION_BLOCKED_MATCH_METHODS
from .domain_validation import is_banned_domain, is_corporate_root_domain, is_infrastructure_domain
from .domain_extraction import (
    _extract_domain_from_correlation,
    _extract_all_domains_from_correlation,
    extract_cmdb_primary_domain
)
from .gates import (
    check_idp_admission,
    check_cmdb_admission,
    check_cloud_admission,
    check_finance_admission,
    check_discovery_admission,
    build_discovery_footprint
)
from .activity import extract_activity_timestamps
from .classification import determine_asset_type, determine_environment
from .debug import build_lens_match_debug
from .result_types import (
    AdmissionResult, AdmissionEvidence, DomainGateResult, DiscoveryInvariantError
)

logger = logging.getLogger(__name__)


def _validate_discovery_invariants(asset, expected_sources: list[str], asset_key: str) -> None:
    """
    Runtime invariants to ensure discovery_sources is the single source of truth.

    FAIL FAST: If any invariant fails, raise DiscoveryInvariantError and stop.
    Do not limp forward with inconsistent state.

    Invariant 1: lens_coverage.discovery == bool(discovery_sources)
    Invariant 2: asset.discovery_sources matches expected sources from footprint
    """
    has_sources = len(expected_sources) > 0

    # Invariant 1: lens_coverage.discovery must equal bool(discovery_sources)
    if asset.lens_coverage.discovery != has_sources:
        raise DiscoveryInvariantError(
            f"INVARIANT_VIOLATION: Asset {asset_key} | "
            f"lens_coverage.discovery={asset.lens_coverage.discovery} but "
            f"discovery_sources={expected_sources} (bool={has_sources}). "
            f"These must agree. Fix: lens_coverage.discovery should derive from discovery_sources."
        )

    # Invariant 2: asset.discovery_sources must match expected sources
    if sorted(asset.discovery_sources) != sorted(expected_sources):
        raise DiscoveryInvariantError(
            f"INVARIANT_VIOLATION: Asset {asset_key} | "
            f"asset.discovery_sources={asset.discovery_sources} but "
            f"expected from footprint={expected_sources}. "
            f"These must agree. Fix: discovery_sources should be set only from footprint."
        )


def _compute_provisioning_status(
    idp_can_admit: bool,
    cmdb_can_admit: bool,
    discovery_admitted: bool,
    finance_can_admit: bool,
    observations: Optional[list[Observation]],
    stale_window_days: int
) -> ProvisioningStatus:
    """
    Compute provisioning status using Traffic Light rules.

    Traffic Light precedence:
    - GREEN (ACTIVE): IdP OR CMDB (with discovery) OR Discovery-only
    - AMBER (REVIEW): CMDB + stale activity, OR Finance
    - RED (QUARANTINE): Cloud/Finance only without corroboration
    """
    has_governance = idp_can_admit or cmdb_can_admit

    # Check if activity is stale (zombie indicator)
    is_stale_activity = False
    if observations:
        latest_activity = None
        for obs in observations:
            if obs.observed_at:
                if latest_activity is None or obs.observed_at > latest_activity:
                    latest_activity = obs.observed_at
        if latest_activity:
            cutoff = datetime.now(timezone.utc) - timedelta(days=stale_window_days)
            if latest_activity.tzinfo is None:
                latest_activity = latest_activity.replace(tzinfo=timezone.utc)
            is_stale_activity = latest_activity < cutoff

    if has_governance:
        if cmdb_can_admit and is_stale_activity and not idp_can_admit:
            return ProvisioningStatus.REVIEW
        return ProvisioningStatus.ACTIVE
    elif discovery_admitted:
        return ProvisioningStatus.ACTIVE
    elif finance_can_admit:
        return ProvisioningStatus.REVIEW
    else:
        return ProvisioningStatus.QUARANTINE


def _check_domain_gates(
    entity: CandidateEntity,
    correlation: CorrelationResult
) -> DomainGateResult:
    """
    Check domain eligibility gates 0, 0.5, and 1.

    Gates:
    - GATE 0: Invalid TLD / internal hostname -> IGNORED
    - GATE 0.5: BANNED_DOMAINS policy -> BLOCKED
    - GATE 1: Corporate root domains -> IGNORED

    Note: Gate 2 (infrastructure domains) requires governance check results
    and is handled separately in apply_admission_criteria.

    Returns:
        DomainGateResult with pass/fail status and domain info
    """
    # Domain recovery
    effective_domain = entity.domain
    recovered_from_correlation = False

    if not effective_domain:
        recovered_domain = _extract_domain_from_correlation(correlation, debug_log=True)
        if recovered_domain:
            effective_domain = recovered_domain
            recovered_from_correlation = True
            entity.domain = effective_domain

    # GATE 0: Invalid TLD / internal hostname
    if effective_domain:
        extracted = extract_domain(effective_domain)
        if not extracted.suffix:
            return DomainGateResult(
                passed=False,
                rejection=AdmissionResult(
                    admitted=False,
                    provisioning_status=ProvisioningStatus.IGNORED,
                    rejection_reason=f"Invalid TLD / Internal hostname: {effective_domain}"
                )
            )
    else:
        return DomainGateResult(
            passed=False,
            rejection=AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason="No resolvable domain - requires domain-first identity"
            )
        )

    # Compute registered domain
    registered_domain = extract_registered_domain(effective_domain)
    if not registered_domain:
        return DomainGateResult(
            passed=False,
            rejection=AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason=f"Cannot extract registered domain from: {effective_domain}"
            )
        )

    # GATE 0.5: BANNED_DOMAINS policy
    if is_banned_domain(registered_domain):
        return DomainGateResult(
            passed=False,
            effective_domain=effective_domain,
            registered_domain=registered_domain,
            rejection=AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.BLOCKED,
                rejection_reason=f"BANNED_DOMAINS policy: {registered_domain} is policy-forbidden"
            )
        )

    # GATE 1: Corporate root domains
    if is_corporate_root_domain(registered_domain):
        return DomainGateResult(
            passed=False,
            effective_domain=effective_domain,
            registered_domain=registered_domain,
            rejection=AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason=f"Corporate root domain: {registered_domain} (from {effective_domain})"
            )
        )

    return DomainGateResult(
        passed=True,
        effective_domain=effective_domain,
        registered_domain=registered_domain,
        recovered_from_correlation=recovered_from_correlation
    )


def _collect_admission_evidence(
    correlation: CorrelationResult,
    observations: Optional[list[Observation]],
    effective_domain: str,
    registered_domain: str,
    entity: CandidateEntity,
    snapshot_timestamp: Optional[datetime],
    policy_config,
    propagated_idp: bool,
    propagated_cmdb: bool
) -> AdmissionEvidence:
    """
    Collect admission evidence from all planes and apply policy adjustments.

    Returns AdmissionEvidence with raw and policy-adjusted admission flags.
    """
    # Check each admission criterion
    idp_admitted, idp_reason = check_idp_admission(
        correlation, entity_registered_domain=registered_domain
    )
    cmdb_admitted, cmdb_reason = check_cmdb_admission(
        correlation,
        require_valid_ci_type=policy_config.admission_gates.require_valid_ci_type,
        require_valid_lifecycle=policy_config.admission_gates.require_valid_lifecycle
    )
    cloud_admitted, cloud_reason = check_cloud_admission(correlation)
    finance_admitted, finance_reason = check_finance_admission(correlation)
    discovery_admitted, discovery_reason = check_discovery_admission(
        observations,
        canonical_key=effective_domain or entity.canonical_name if entity else None,
        snapshot_timestamp=snapshot_timestamp
    )

    footprint = build_discovery_footprint(
        observations,
        canonical_key=effective_domain or entity.canonical_name if entity else None,
        snapshot_timestamp=snapshot_timestamp
    )

    # Policy toggles
    enable_vendor_propagation = policy_config.admission_gates.enable_vendor_propagation
    allow_finance_only = policy_config.admission_gates.allow_finance_only_admission
    finance_requires_discovery = policy_config.admission_gates.finance_requires_discovery
    require_corroboration = policy_config.admission_gates.require_corroboration
    noise_floor = policy_config.admission_gates.noise_floor

    # Discovery admission adjustment
    if not require_corroboration and len(footprint.discovery_sources) >= noise_floor:
        discovery_admitted = True

    # Finance admission policy
    if allow_finance_only:
        finance_can_admit = finance_admitted
    elif not finance_requires_discovery:
        finance_can_admit = finance_admitted and (
            idp_admitted or cmdb_admitted or cloud_admitted or True
        )
    else:
        finance_can_admit = finance_admitted and (
            idp_admitted or cmdb_admitted or cloud_admitted or discovery_admitted
        )

    # Vendor propagation
    if enable_vendor_propagation:
        idp_can_admit = idp_admitted or propagated_idp
        cmdb_can_admit = cmdb_admitted or propagated_cmdb
    else:
        idp_can_admit = idp_admitted
        cmdb_can_admit = cmdb_admitted

    return AdmissionEvidence(
        idp_admitted=idp_admitted,
        idp_reason=idp_reason,
        cmdb_admitted=cmdb_admitted,
        cmdb_reason=cmdb_reason,
        cloud_admitted=cloud_admitted,
        cloud_reason=cloud_reason,
        finance_admitted=finance_admitted,
        finance_reason=finance_reason,
        discovery_admitted=discovery_admitted,
        discovery_reason=discovery_reason,
        footprint=footprint,
        idp_can_admit=idp_can_admit,
        cmdb_can_admit=cmdb_can_admit,
        finance_can_admit=finance_can_admit
    )


def _build_admitted_asset(
    entity: CandidateEntity,
    correlation: CorrelationResult,
    evidence: AdmissionEvidence,
    provisioning_status: ProvisioningStatus,
    effective_domain: str,
    registered_domain: str,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    observations: Optional[list[Observation]],
    propagated_idp: bool,
    propagated_cmdb: bool,
    propagation_reason: Optional[str],
    idp_activity_map: Optional[dict[str, datetime]],
    recovered_from_correlation: bool
) -> Asset:
    """
    Build the admitted Asset object with all metadata.

    Constructs identifiers, tags, lens status/coverage, and activity evidence.
    """
    # Build admission reasons
    admission_reasons = []
    if evidence.idp_admitted:
        admission_reasons.append(evidence.idp_reason)
    if evidence.cmdb_admitted:
        admission_reasons.append(evidence.cmdb_reason)
    if evidence.cloud_admitted:
        admission_reasons.append(evidence.cloud_reason)
    if evidence.finance_admitted:
        admission_reasons.append(evidence.finance_reason)
    if evidence.discovery_admitted:
        admission_reasons.append(evidence.discovery_reason)
    if propagation_reason and (propagated_idp or propagated_cmdb):
        admission_reasons.append(f"Vendor governance: {propagation_reason}")

    # Build lens status with propagated governance
    idp_status = correlation.idp.status.value
    if propagated_idp and correlation.idp.status == MatchStatus.UNMATCHED:
        idp_status = MatchStatus.MATCHED.value

    cmdb_status = correlation.cmdb.status.value
    if propagated_cmdb and correlation.cmdb.status == MatchStatus.UNMATCHED:
        cmdb_status = MatchStatus.MATCHED.value

    lens_status = LensStatuses(
        idp=LensStatus(idp_status),
        cmdb=LensStatus(cmdb_status),
        cloud=LensStatus(correlation.cloud.status.value),
        finance=LensStatus(correlation.finance.status.value)
    )

    # Discovery sources
    discovery_sources_list = sorted(evidence.footprint.discovery_sources)

    # Lens coverage - DIRECT matches only, NOT from vendor propagation
    lens_coverage = LensCoverage(
        idp=evidence.idp_admitted,
        cmdb=evidence.cmdb_admitted,
        cloud=evidence.cloud_admitted,
        finance=evidence.finance_admitted,
        discovery=bool(discovery_sources_list),
        vendor_governed=propagated_idp or propagated_cmdb
    )

    # Build domain list with provenance tracking
    domain_list = []
    domain_provenance = {}
    seen_domains = set()

    # Step 1: Add discovery domain (highest priority)
    if effective_domain:
        normalized = effective_domain.lower().strip()
        domain_list.append(normalized)
        seen_domains.add(normalized)
        entity_is_discovery = getattr(entity, 'source', 'discovery') == 'discovery'
        entity_has_discovery_obs = bool(entity.observation_ids) if entity else False

        if recovered_from_correlation and not (entity_is_discovery or entity_has_discovery_obs):
            if correlation.idp.status == MatchStatus.MATCHED:
                domain_provenance[normalized] = "idp"
            elif correlation.cmdb.status == MatchStatus.MATCHED:
                domain_provenance[normalized] = "cmdb"
            else:
                domain_provenance[normalized] = "inferred"
        else:
            domain_provenance[normalized] = "discovery"

    # Step 2: Promote CMDB primary domain if not already in list
    cmdb_match_method = correlation.cmdb.match_method if correlation.cmdb else None
    cmdb_is_authoritative = cmdb_match_method in PROMOTION_ALLOWED_MATCH_METHODS
    cmdb_is_heuristic = cmdb_match_method in PROMOTION_BLOCKED_MATCH_METHODS

    cmdb_primary, cmdb_valid = extract_cmdb_primary_domain(
        correlation,
        is_authoritative_match=evidence.cmdb_admitted and cmdb_is_authoritative
    )

    # Block domain promotion for heuristic match methods
    if cmdb_primary and cmdb_is_heuristic:
        logger.info(
            f"DOMAIN_PROMOTION_BLOCKED entity={entity.original_name} "
            f"blocked_domain={cmdb_primary} match_method={cmdb_match_method} "
            f"reason=HEURISTIC_MATCH_NOT_AUTHORITATIVE"
        )
        cmdb_primary = None

    if cmdb_primary and cmdb_valid and cmdb_primary not in seen_domains:
        domain_list.append(cmdb_primary)
        seen_domains.add(cmdb_primary)
        domain_provenance[cmdb_primary] = "cmdb"
        logger.debug(
            f"CMDB_DOMAIN_PROMOTED entity={entity.original_name} "
            f"cmdb_domain={cmdb_primary} discovery_domain={effective_domain} "
            f"authoritative={evidence.cmdb_admitted} match_method={cmdb_match_method}"
        )

    # Extract plane domains for reference/enrichment only
    plane_domains = _extract_all_domains_from_correlation(correlation)
    reference_domains = [pd for pd in plane_domains if pd not in seen_domains]

    identifiers = AssetIdentifiers(
        domains=domain_list,
        hostnames=[entity.hostname] if entity.hostname else [],
        uris=[entity.uri] if entity.uri else [],
        reference_domains=reference_domains,
        domain_provenance=domain_provenance
    )

    # Build tags
    tags = []
    if evidence.idp_admitted:
        tags.append("identity_managed")
    if evidence.cmdb_admitted:
        tags.append("cmdb_registered")
    if evidence.cloud_admitted:
        tags.append("cloud_hosted")
    if evidence.finance_admitted:
        tags.append("finance_tracked")
    if evidence.discovery_admitted:
        tags.append("discovery_only")
    tags.append(f"traffic_light:{provisioning_status.value}")

    # Activity evidence
    activity_evidence = extract_activity_timestamps(
        correlation, entity, observations, idp_activity_map, propagated_idp
    )

    # Vendor hypothesis
    vendor_hypothesis = None
    if entity.vendor_hypothesis:
        vendor_hypothesis = VendorHypothesis(
            value=entity.vendor_hypothesis.value,
            confidence=entity.vendor_hypothesis.confidence,
            basis=entity.vendor_hypothesis.basis
        )

    # Key selection (discovery domains only)
    discovery_domains = [d for d in domain_list if domain_provenance.get(d) == "discovery"]

    if not discovery_domains:
        asset_key = registered_domain
    else:
        registered_candidates = set()
        for domain in discovery_domains:
            reg = extract_registered_domain(domain)
            if reg:
                registered_candidates.add(reg)
            else:
                registered_candidates.add(domain)

        if registered_candidates:
            sorted_candidates = sorted(registered_candidates)
            asset_key = sorted_candidates[0]
            logger.debug(
                f"KEY_SELECTION: entity={entity.original_name} "
                f"discovery_domains={discovery_domains} candidates={sorted_candidates} "
                f"selected={asset_key} (lexicographic, no collapse)"
            )
        else:
            asset_key = registered_domain

    if os.environ.get("AOD_DEBUG_KEYS"):
        logger.info("admission.primary_key_freeze", extra={
            "entity_domain": entity.domain,
            "registered_domain": registered_domain,
            "asset_key": asset_key,
            "from_correlation_recovery": recovered_from_correlation,
            "key_selection_contract": "v2.0"
        })

    asset = Asset(
        asset_id=deterministic_uuid(snapshot_id, run_id, "asset", asset_key),
        tenant_id=tenant_id,
        run_id=run_id,
        name=entity.original_name,
        asset_type=determine_asset_type(correlation, entity),
        identifiers=identifiers,
        vendor=entity.vendor,
        vendor_hypothesis=vendor_hypothesis,
        environment=determine_environment(correlation),
        evidence_refs=correlation.all_evidence_refs(),
        lens_status=lens_status,
        lens_coverage=lens_coverage,
        lens_match_debug=build_lens_match_debug(correlation),
        activity_evidence=activity_evidence,
        tags=tags,
        admission_reason="; ".join(admission_reasons),
        provisioning_status=provisioning_status,
        discovery_sources=discovery_sources_list
    )

    _validate_discovery_invariants(asset, discovery_sources_list, asset_key)

    return asset


def apply_admission_criteria(
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    observations: Optional[list[Observation]] = None,
    propagated_idp: bool = False,
    propagated_cmdb: bool = False,
    propagation_reason: Optional[str] = None,
    idp_activity_map: Optional[dict[str, datetime]] = None,
    snapshot_timestamp: Optional[datetime] = None,
    fabric_plane_domains: Optional[set[str]] = None
) -> AdmissionResult:
    """
    Apply admission criteria to determine if entity should be admitted as asset.

    Uses composable helpers for testability:
    - _check_domain_gates(): Gates 0, 0.5, 1 (TLD, banned, corporate)
    - _collect_admission_evidence(): All plane checks + policy application
    - _compute_provisioning_status(): Traffic light logic
    - _build_admitted_asset(): Asset construction

    Admission criteria (at least one required):
    - IdP: match with SSO/SCIM/service_principal
    - CMDB: match with valid ci_type and lifecycle
    - Cloud: match with real resource type
    - Finance: match with contract/transaction evidence
    - Discovery: ≥2 distinct sources with recent activity

    Args:
        fabric_plane_domains: Set of domains for Farm-declared fabric plane
            controllers. These bypass banned/infrastructure domain gates since
            Farm is the authoritative source for fabric planes.

    Returns:
        AdmissionResult indicating whether entity is admitted
    """
    entity = correlation.entity

    # STEP 1: Domain gates (0, 0.5, 1)
    # Fabric plane controller domains bypass Gates 0.5 (banned) and 1 (corporate)
    # because Farm authoritatively declares these as infrastructure controllers
    gate_result = _check_domain_gates(entity, correlation)
    if not gate_result.passed:
        registered = gate_result.registered_domain
        is_fabric_bypass = (
            fabric_plane_domains
            and registered
            and registered in fabric_plane_domains
        )
        if not is_fabric_bypass:
            return gate_result.rejection

    effective_domain = gate_result.effective_domain
    registered_domain = gate_result.registered_domain

    # STEP 2: Load policy and check IdP/CMDB for gate 2
    from ...core.policy.loader import get_current_config
    policy_config = get_current_config()

    idp_admitted, _ = check_idp_admission(correlation, entity_registered_domain=registered_domain)
    cmdb_admitted, _ = check_cmdb_admission(
        correlation,
        require_valid_ci_type=policy_config.admission_gates.require_valid_ci_type,
        require_valid_lifecycle=policy_config.admission_gates.require_valid_lifecycle
    )

    # GATE 2: Infrastructure domains without governance
    # Fabric plane controller domains bypass this gate (Farm-authoritative)
    is_fabric_domain = (
        fabric_plane_domains
        and registered_domain
        and registered_domain in fabric_plane_domains
    )
    if is_infrastructure_domain(registered_domain) and not is_fabric_domain:
        if not (idp_admitted or cmdb_admitted):
            return AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason=f"Infrastructure domain without governance: {registered_domain} (from {effective_domain})"
            )

    # STEP 3: Collect all admission evidence
    evidence = _collect_admission_evidence(
        correlation=correlation,
        observations=observations,
        effective_domain=effective_domain,
        registered_domain=registered_domain,
        entity=entity,
        snapshot_timestamp=snapshot_timestamp,
        policy_config=policy_config,
        propagated_idp=propagated_idp,
        propagated_cmdb=propagated_cmdb
    )

    # STEP 4: Check if any admission criteria satisfied
    # Farm-declared fabric plane controllers are auto-admitted (Farm authority)
    fabric_plane_auto_admit = (
        is_fabric_domain
        and entity.entity_id.startswith("fabric_controller_")
    )
    if not fabric_plane_auto_admit and not any([
        evidence.idp_can_admit,
        evidence.cmdb_can_admit,
        evidence.cloud_admitted,
        evidence.finance_can_admit,
        evidence.discovery_admitted
    ]):
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.IGNORED,
            rejection_reason="No admission criteria satisfied"
        )

    # STEP 5: Compute traffic light status
    stale_window_days = policy_config.admission_gates.stale_window_days
    provisioning_status = _compute_provisioning_status(
        idp_can_admit=evidence.idp_can_admit,
        cmdb_can_admit=evidence.cmdb_can_admit,
        discovery_admitted=evidence.discovery_admitted,
        finance_can_admit=evidence.finance_can_admit,
        observations=observations,
        stale_window_days=stale_window_days
    )

    # STEP 6: Build the admitted asset
    asset = _build_admitted_asset(
        entity=entity,
        correlation=correlation,
        evidence=evidence,
        provisioning_status=provisioning_status,
        effective_domain=effective_domain,
        registered_domain=registered_domain,
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id=snapshot_id,
        observations=observations,
        propagated_idp=propagated_idp,
        propagated_cmdb=propagated_cmdb,
        propagation_reason=propagation_reason,
        idp_activity_map=idp_activity_map,
        recovered_from_correlation=gate_result.recovered_from_correlation
    )

    # Build admission reason string
    admission_reasons = []
    if evidence.idp_admitted:
        admission_reasons.append(evidence.idp_reason)
    if evidence.cmdb_admitted:
        admission_reasons.append(evidence.cmdb_reason)
    if evidence.cloud_admitted:
        admission_reasons.append(evidence.cloud_reason)
    if evidence.finance_admitted:
        admission_reasons.append(evidence.finance_reason)
    if evidence.discovery_admitted:
        admission_reasons.append(evidence.discovery_reason)
    if propagation_reason and (propagated_idp or propagated_cmdb):
        admission_reasons.append(f"Vendor governance: {propagation_reason}")

    return AdmissionResult(
        admitted=True,
        provisioning_status=provisioning_status,
        asset=asset,
        admission_reason="; ".join(admission_reasons)
    )
