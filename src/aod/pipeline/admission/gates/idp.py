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

            # INVARIANT 2: No-domain IdP matches NEVER grant governance
            # IdP record must have an explicit domain to assert governance
            # Check both record.domain and record.canonical_domain (Farm's correlation field)
            idp_domain = None
            if record.domain:
                idp_domain = extract_registered_domain(record.domain)
            elif getattr(record, 'canonical_domain', None):
                idp_domain = extract_registered_domain(record.canonical_domain)

            if not idp_domain:
                # IdP has no domain - cannot grant governance (name-only match)
                if debug_match:
                    logging.info(
                        f"[GOVERNANCE_GATE] IdP no-domain match blocked: entity={entity_registered_domain} "
                        f"idp_name={record.name} (no domain or canonical_domain on IdP record)"
                    )
                continue  # Skip this record, try next

            if _idp_domain_matches_entity(idp_domain, entity_registered_domain, idp_name=record.name):
                # Domain-aligned match - check for SSO/SCIM as stronger signal
                if record.has_sso:
                    return True, "IdP match with SSO enabled (domain-aligned governance)"
                if record.has_scim:
                    return True, "IdP match with SCIM enabled (domain-aligned governance)"
                # Domain-aligned match without SSO/SCIM still counts
                return True, "IdP match with domain-aligned governance"

    # Cross-domain IdP matches (even with SSO/SCIM) do NOT provide admission governance
    return False, ""
