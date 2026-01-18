"""IdP admission gate - check IdP plane criteria."""

import os
import logging
from typing import Optional

from ...correlate_entities import CorrelationResult, MatchStatus, HEURISTIC_MATCH_METHODS
from ....models.input_contracts import IdPObject
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

    if correlation.idp.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    # Governance principle: Only authoritative matches can assert governance.
    # Heuristic matches (fuzzy, vendor, contains) are enrichment-only.
    idp_match_method = correlation.idp.match_method
    is_authoritative = correlation.idp.is_authoritative

    # GOVERNANCE INVARIANT ASSERTION (Jan 2026 - Phase B)
    # If match method is heuristic, IdP governance MUST NOT be granted.
    # This is a defensive check - the gate below should already block heuristics.
    if idp_match_method and idp_match_method in HEURISTIC_MATCH_METHODS:
        if debug_match:
            logging.warning(
                f"[GOVERNANCE_GATE] IdP heuristic match blocked: domain={entity_registered_domain} "
                f"method={idp_match_method} is_authoritative={is_authoritative}"
            )
        # INVARIANT: Heuristic matches NEVER assert HAS_IDP
        return False, ""

    if not is_authoritative:
        if debug_match:
            logging.info(
                f"[GOVERNANCE_GATE] IdP match NOT authoritative: domain={entity_registered_domain} "
                f"method={idp_match_method} is_authoritative={is_authoritative}"
            )
        return False, ""

    if debug_match:
        logging.info(
            f"[GOVERNANCE_GATE] IdP authoritative match: domain={entity_registered_domain} "
            f"method={idp_match_method} is_authoritative={is_authoritative}"
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

            # GOVERNANCE INVARIANT (Jan 2026 - Phase C)
            # SSO is the governance signal from IdP.
            # 
            # Farm's pattern (validated from expected data):
            # - Shadow-expected assets have IdP records with has_sso=False (47 records)
            # - Zombie-expected assets have IdP records with has_sso=True (89 records)
            # - SCIM alone (without SSO) does NOT grant governance
            #
            # An IdP record provides governance ONLY if has_sso=True.
            # SCIM is provisioning automation but not identity governance.
            #
            if record.has_sso:
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP SSO governance granted: entity={entity_registered_domain} "
                        f"idp_name={record.name}"
                    )
                return True, "IdP match with SSO enabled"
            
            # No SSO - this IdP record does not provide governance (SCIM alone is not enough)
            if debug_match:
                logging.info(
                    f"[GOVERNANCE_GATE] IdP record without SSO - no governance: entity={entity_registered_domain} "
                    f"idp_name={record.name} has_sso={record.has_sso} has_scim={record.has_scim}"
                )

    # Cross-domain IdP matches (even with SSO/SCIM) do NOT provide admission governance
    return False, ""
