"""IdP admission gate - check IdP plane criteria."""

import os
import logging
from typing import Optional

from ...correlate_entities import CorrelationResult, MatchStatus, HEURISTIC_MATCH_METHODS
from ....models.input_contracts import IdPObject
from ....core.policy.loader import get_current_config
from ...vendor_inference import extract_registered_domain
from ..constants import NON_CANONICAL_IDP_TOKENS
from ..idp_helpers import _extract_idp_domain, _idp_domain_matches_entity


def is_non_canonical_idp_app(app_name: Optional[str]) -> bool:
    """
    Check if IdP app name indicates a non-canonical application.

    Non-canonical apps (legacy, prod, dev, staging, deprecated) should NOT
    grant governance even if the domain matches exactly. These suffixes
    indicate the IdP record is not the primary/canonical application.

    Examples:
    - "Primeway-prod" → non-canonical (production environment, not main app)
    - "Bignest (Legacy)" → non-canonical (deprecated/old version)
    - "Cloudsync" → canonical (clean name)
    - "Zendesk" → canonical (clean name)

    Returns True if the app is non-canonical and should NOT grant governance.
    """
    if not app_name:
        return False

    normalized = app_name.strip().lower()
    return any(tok in normalized for tok in NON_CANONICAL_IDP_TOKENS)


def check_idp_admission(
    correlation: CorrelationResult,
    entity_registered_domain: Optional[str] = None
) -> tuple[bool, str]:
    """
    Check IdP plane admission criteria:
    - IdP match with DOMAIN-ALIGNED governance (exact domain match required)
    - SSO/SCIM provides stronger confidence but STILL requires domain alignment
    NOTE: Both MATCHED and AMBIGUOUS count as having IdP evidence.

    Farm requires domain-aligned IdP for admission, NOT cross-domain matches.
    SSO/SCIM does NOT override domain alignment - it's a stronger signal FOR domain-aligned matches.

    Cross-domain IdP matches (e.g., fastbox.cloud matched to fastbox.ai IdP) do NOT
    provide governance for admission, even if the IdP has SSO/SCIM enabled.
    Farm's decision traces confirm: idp_present=False for cross-domain matches.

    Jan 2026: Governance principle - only AUTHORITATIVE matches can assert governance.
    Heuristic matches (fuzzy, vendor, contains) provide enrichment but not governance.

    Examples:
    - fastbox.cloud entity + fastbox.ai IdP with SSO → NOT admitted (cross-domain)
    - fastbox.cloud entity + fastbox.cloud IdP with SSO → admitted (domain-aligned + SSO)
    - easyworks.ai entity + easyworks.ai IdP → admitted (exact match)
    """
    debug_match = os.environ.get("AOD_DEBUG_MATCH", "").lower() in ("1", "true", "yes")
    
    # Load policy configuration for IdP governance
    config = get_current_config()
    trust_heuristic = config.idp_governance.trust_heuristic_matches
    heuristic_requires_sso = config.idp_governance.heuristic_requires_sso
    require_sso_for_authoritative = config.idp_governance.require_sso_for_authoritative_matches

    if correlation.idp.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    # Governance principle: Only authoritative matches can assert governance.
    # Heuristic matches (fuzzy, vendor, contains) are enrichment-only.
    idp_match_method = correlation.idp.match_method
    is_authoritative = correlation.idp.is_authoritative
    is_heuristic_match = idp_match_method and idp_match_method in HEURISTIC_MATCH_METHODS

    # GOVERNANCE POLICY CHECK (Jan 2026 - Policy Variable)
    # By default (strict mode), heuristic matches do NOT grant governance.
    # If trust_heuristic_matches=True (loose mode), heuristic matches CAN grant governance.
    if is_heuristic_match:
        if not trust_heuristic:
            # STRICT MODE: Heuristic matches NEVER assert HAS_IDP
            if debug_match:
                logging.warning(
                    f"[GOVERNANCE_GATE] IdP heuristic match blocked (strict mode): domain={entity_registered_domain} "
                    f"method={idp_match_method} is_authoritative={is_authoritative} trust_heuristic={trust_heuristic}"
                )
            return False, ""
        else:
            # LOOSE MODE: Heuristic matches CAN grant governance
            if debug_match:
                logging.info(
                    f"[GOVERNANCE_GATE] IdP heuristic match ALLOWED (loose mode): domain={entity_registered_domain} "
                    f"method={idp_match_method} trust_heuristic={trust_heuristic}"
                )
            # Continue to SSO check below - heuristic matches may still require SSO

    if not is_authoritative and not (is_heuristic_match and trust_heuristic):
        if debug_match:
            logging.info(
                f"[GOVERNANCE_GATE] IdP match NOT authoritative: domain={entity_registered_domain} "
                f"method={idp_match_method} is_authoritative={is_authoritative}"
            )
        return False, ""

    if debug_match:
        logging.info(
            f"[GOVERNANCE_GATE] IdP match proceeding: domain={entity_registered_domain} "
            f"method={idp_match_method} is_authoritative={is_authoritative} is_heuristic={is_heuristic_match}"
        )

    for record in correlation.idp.matched_records:
        if isinstance(record, IdPObject):
            # INVARIANT 1: Non-canonical IdP apps NEVER grant governance
            # Applies to ALL match paths - even exact domain matches
            if is_non_canonical_idp_app(record.name):
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP non-canonical app blocked: domain={entity_registered_domain} "
                        f"idp_name={record.name} (contains legacy/prod/dev/staging suffix)"
                    )
                continue  # Skip this record, try next

            # INVARIANT 2: Domain alignment required for governance
            # IdP governance requires explicit domain on the IdP record that
            # aligns with the entity domain. Cross-domain matches do not
            # provide governance (I3 provenance rule).
            # No-domain IdP records cannot grant governance — name-only
            # matches are for enrichment/correlation, not security assertion.
            idp_domain = _extract_idp_domain(record)
            if idp_domain is None:
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP record has no domain - cannot grant governance: "
                        f"entity={entity_registered_domain} idp_name={record.name}"
                    )
                continue  # No-domain IdP records are informational only
            if not _idp_domain_matches_entity(idp_domain, entity_registered_domain, record.name):
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP domain not aligned: entity={entity_registered_domain} "
                        f"idp_domain={idp_domain} idp_name={record.name}"
                    )
                continue  # Skip this record, try next

            # GOVERNANCE INVARIANT (Jan 2026 - Phase C, with Policy Variable)
            # SSO is the governance signal from IdP.
            # 
            # Farm's pattern (validated from expected data):
            # - Shadow-expected assets have IdP records with has_sso=False (47 records)
            # - Zombie-expected assets have IdP records with has_sso=True (89 records)
            # - SCIM alone (without SSO) does NOT grant governance
            #
            # Policy controls for heuristic matches:
            # - If trust_heuristic_matches=True AND heuristic_requires_sso=False,
            #   heuristic matches can grant governance even without SSO
            # - Otherwise, SSO is required
            #
            requires_sso = True  # Default: always require SSO
            if is_authoritative and not require_sso_for_authoritative:
                # Authoritative match quality is sufficient — SSO not required
                requires_sso = False
            elif is_heuristic_match and trust_heuristic and not heuristic_requires_sso:
                # Loose mode with heuristic match AND SSO not required
                requires_sso = False
            
            if record.has_sso:
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP domain-aligned SSO governance granted: entity={entity_registered_domain} "
                        f"idp_name={record.name} is_heuristic={is_heuristic_match}"
                    )
                return True, "domain-aligned IdP match with SSO enabled"
            
            # No SSO - check if this match can still grant governance
            if not requires_sso:
                if is_authoritative:
                    if debug_match:
                        logging.info(
                            f"[GOVERNANCE_GATE] IdP authoritative governance granted (no SSO required): entity={entity_registered_domain} "
                            f"idp_name={record.name} method={idp_match_method}"
                        )
                    return True, "domain-aligned IdP authoritative match (SSO not required for authoritative)"
                else:
                    if debug_match:
                        logging.info(
                            f"[GOVERNANCE_GATE] IdP heuristic governance granted (no SSO required): entity={entity_registered_domain} "
                            f"idp_name={record.name} is_heuristic={is_heuristic_match}"
                        )
                    return True, "domain-aligned IdP heuristic match (SSO not required by policy)"
            
            # No SSO - this IdP record does not provide governance (SCIM alone is not enough)
            if debug_match:
                logging.info(
                    f"[GOVERNANCE_GATE] IdP record without SSO - no governance: entity={entity_registered_domain} "
                    f"idp_name={record.name} has_sso={record.has_sso} has_scim={record.has_scim}"
                )

    # Cross-domain IdP matches (even with SSO/SCIM) do NOT provide admission governance
    return False, ""
