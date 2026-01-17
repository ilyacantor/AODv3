"""Result types and data classes for correlation."""

from dataclasses import dataclass, field
from typing import Optional

from .enums import MatchStatus, AmbiguityCode, MatchQuality
from ..normalize_observations import CandidateEntity
from ...models.input_contracts import PlaneRecord


@dataclass
class RelatedDomainVariant:
    """
    Relationship metadata for cross-TLD domain variants.

    When brand-token matching finds a related domain (e.g., netcloud.com matches
    record with netcloud.io), this stores the relationship WITHOUT triggering
    identity merge. This is enrichment metadata only.
    """
    entity_domain: str  # The entity's registered domain (e.g., netcloud.com)
    related_domain: str  # The related domain from the record (e.g., netcloud.io)
    match_basis: str  # How they matched: "first_token", "collapsed_brand"
    record_id: str  # The matched record ID
    plane: str  # Which plane: "idp", "cmdb", "cloud", "finance"


@dataclass
class PlaneMatch:
    """Match result for a single plane."""
    status: MatchStatus
    matched_ids: list[str] = field(default_factory=list)
    matched_records: list[PlaneRecord] = field(default_factory=list)
    match_method: Optional[str] = None
    match_key: Optional[str] = None
    ambiguity_code: AmbiguityCode = AmbiguityCode.NONE
    disambiguation_detail: Optional[str] = None
    # Cross-TLD relationships (enrichment only, never identity merge)
    related_domain_variants: list[RelatedDomainVariant] = field(default_factory=list)

    @property
    def match_quality(self) -> MatchQuality:
        """
        Determine if this match is authoritative or heuristic based on match_method.

        AUTHORITATIVE matches (domain, uri, canonical_name) can grant governance.
        HEURISTIC matches (fuzzy, vendor, contains, etc.) are enrichment-only.
        """
        if self.status == MatchStatus.UNMATCHED:
            return MatchQuality.NONE
        return MatchQuality.from_match_method(self.match_method)

    @property
    def is_authoritative(self) -> bool:
        """Convenience property: True if this match can assert governance."""
        return self.match_quality == MatchQuality.AUTHORITATIVE


@dataclass
class CorrelationResult:
    """Correlation result for an entity across all planes."""
    entity: CandidateEntity
    idp: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cmdb: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cloud: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    finance: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))

    def all_evidence_refs(self) -> list[str]:
        """Get all evidence references from matched planes.

        For finance plane, ALSO adds 'recurring_' prefixed refs for records
        with is_recurring=True. Original IDs are always preserved for
        downstream consumers (findings, UI).

        NOTE: Both MATCHED and AMBIGUOUS statuses count as having evidence,
        consistent with admission logic in check_*_admission functions.
        """
        from ...models.input_contracts import Contract, Transaction

        refs = list(self.entity.observation_ids)
        for plane_match in [self.idp, self.cmdb, self.cloud]:
            if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                refs.extend(plane_match.matched_ids)

        if self.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            refs.extend(self.finance.matched_ids)

            for i, record_id in enumerate(self.finance.matched_ids):
                record = self.finance.matched_records[i] if i < len(self.finance.matched_records) else None
                if record:
                    if isinstance(record, Contract):
                        if record.is_recurring:
                            raw_id = record_id.removeprefix("contract:")
                            refs.append(f"recurring_contract:{raw_id}")
                    elif isinstance(record, Transaction):
                        if record.is_recurring:
                            raw_id = record_id.removeprefix("transaction:")
                            refs.append(f"recurring_transaction:{raw_id}")

        return refs


@dataclass
class PrecomputedEntityData:
    """Pre-computed data for an entity to avoid repeated calculations."""
    registered_domain: Optional[str] = None
    domain_token: str = ""
    canonical_vendor: Optional[str] = None
    normalization_token: str = ""
