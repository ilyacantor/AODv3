"""Tests for the COFA deterministic pre-filter."""

from decimal import Decimal

import pytest

from src.maestra.agents.cofa.prefilter import (
    COFAObject,
    normalize_domain,
    normalize_duns,
    normalize_name,
    normalize_tax_id,
    run_prefilter,
)


# ======================================================================
# Helper
# ======================================================================
def _obj(
    object_type: str = "customer",
    entity_source: str = "entity_a",
    name: str = "Unnamed",
    **kwargs,
) -> COFAObject:
    """Shortcut to build a COFAObject with sensible defaults."""
    return COFAObject(
        object_type=object_type,
        entity_source=entity_source,
        name=name,
        **kwargs,
    )


# ======================================================================
# Normalization Tests
# ======================================================================
class TestNormalization:
    def test_normalize_strips_punctuation(self):
        assert normalize_name("Acme, Inc.") == "acme"

    def test_normalize_removes_suffixes(self):
        assert normalize_name("Acme Corporation LLC") == "acme"

    def test_normalize_collapses_whitespace(self):
        assert normalize_name("  Acme   Corp  ") == "acme"

    def test_normalize_domain(self):
        assert normalize_domain("www.Acme.COM") == "acme.com"

    def test_normalize_tax_id(self):
        assert normalize_tax_id("12-3456789") == "123456789"

    def test_normalize_duns(self):
        assert normalize_duns("08-146-1234") == "081461234"


# ======================================================================
# Matching Tests
# ======================================================================
class TestMatching:
    def test_exact_name_match(self):
        """'Acme Inc' vs 'ACME INCORPORATED' match by normalized name."""
        result = run_prefilter(
            [_obj(name="Acme Inc", entity_source="ea")],
            [_obj(name="ACME INCORPORATED", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "name"
        assert m.confidence == Decimal("1.0")
        assert m.source == "pre-filter"
        assert result.ambiguous_remainder_a == []
        assert result.ambiguous_remainder_b == []

    def test_tax_id_match_different_names(self):
        """Same tax_id, different names → match via tax_id."""
        result = run_prefilter(
            [_obj(name="Acme Solutions", tax_id="123456789", entity_source="ea")],
            [_obj(name="Acme Global", tax_id="12-345-6789", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "tax_id"

    def test_domain_match_different_names(self):
        """Same domain, different names → match via domain."""
        result = run_prefilter(
            [_obj(name="Acme", domain="acme.com", entity_source="ea")],
            [_obj(name="Acme Global Services", domain="www.acme.com", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "domain"

    def test_duns_match(self):
        """Same DUNS, different names → match via duns."""
        result = run_prefilter(
            [_obj(name="Alpha Co", duns="081461234", entity_source="ea")],
            [_obj(name="Beta LLC", duns="08-146-1234", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "duns"

    def test_no_match(self):
        """Completely different objects → no match, both in remainder."""
        result = run_prefilter(
            [_obj(name="Alpha Corp", entity_source="ea")],
            [_obj(name="Beta Industries", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 0
        assert len(result.ambiguous_remainder_a) == 1
        assert len(result.ambiguous_remainder_b) == 1

    def test_cross_type_never_matches(self):
        """Customer 'Acme' and vendor 'Acme' are never compared."""
        result = run_prefilter(
            [_obj(object_type="customer", name="Acme", entity_source="ea")],
            [_obj(object_type="vendor", name="Acme", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 0
        assert len(result.ambiguous_remainder_a) == 1
        assert len(result.ambiguous_remainder_b) == 1

    def test_ambiguous_multi_match(self):
        """Entity A 'Acme' matches two Entity B objects by domain → ambiguous."""
        result = run_prefilter(
            [_obj(name="Acme", domain="acme.com", entity_source="ea")],
            [
                _obj(name="Acme East", domain="acme.com", entity_source="eb"),
                _obj(name="Acme West", domain="acme.com", entity_source="eb"),
            ],
        )
        # No deterministic match — routed to ambiguous
        assert len(result.deterministic_matches) == 0
        assert len(result.ambiguous_remainder_a) == 1
        assert len(result.ambiguous_remainder_b) == 2
        # Ambiguity flag present
        assert any("Ambiguous" in f for f in result.truncation_flags)

    def test_one_to_one_constraint(self):
        """Entity A 'Acme' matches B 'Acme Inc' by name and B 'Acme Corp' by domain.

        Name has higher priority than domain → takes name match.
        """
        result = run_prefilter(
            [_obj(name="Acme Inc", domain="acme.com", entity_source="ea")],
            [
                _obj(name="ACME INCORPORATED", domain="other.com", entity_source="eb"),
                _obj(name="Totally Different", domain="acme.com", entity_source="eb"),
            ],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "name"
        assert m.entity_b_name == "ACME INCORPORATED"
        # The domain-match object is in remainder
        assert len(result.ambiguous_remainder_b) == 1
        assert result.ambiguous_remainder_b[0].name == "Totally Different"


# ======================================================================
# Truncation Tests
# ======================================================================
class TestTruncation:
    def test_truncation_customers_by_revenue(self):
        """150 customers → top 100 by revenue kept."""
        a_objects = [
            _obj(
                name=f"Customer {i}",
                entity_source="ea",
                revenue=Decimal(str(i * 1000)),
            )
            for i in range(150)
        ]
        b_objects = [_obj(name="Nobody", entity_source="eb")]

        result = run_prefilter(a_objects, b_objects)

        # All Entity A customers in remainder (none match "Nobody")
        # but only 100 of them — the top 100 by revenue
        a_remainder_names = {o.name for o in result.ambiguous_remainder_a}
        assert len(result.ambiguous_remainder_a) == 100
        # The lowest-revenue customers (0..49) should have been truncated
        for i in range(50):
            assert f"Customer {i}" not in a_remainder_names
        # The highest-revenue customers (50..149) should be present
        for i in range(50, 150):
            assert f"Customer {i}" in a_remainder_names

    def test_truncation_flag_generated(self):
        """Truncation flag message is correct."""
        a_objects = [
            _obj(
                name=f"Customer {i}",
                entity_source="ea",
                revenue=Decimal(str(i)),
            )
            for i in range(150)
        ]
        result = run_prefilter(a_objects, [])
        assert len(result.truncation_flags) == 1
        assert "customer list for entity ea truncated from 150 to 100" in result.truncation_flags[0].lower()

    def test_no_truncation_under_100(self):
        """80 customers → no truncation, no flag."""
        a_objects = [
            _obj(name=f"Customer {i}", entity_source="ea")
            for i in range(80)
        ]
        result = run_prefilter(a_objects, [])
        assert len(result.truncation_flags) == 0
        assert len(result.ambiguous_remainder_a) == 80


# ======================================================================
# Edge Cases
# ======================================================================
class TestEdgeCases:
    def test_empty_list(self):
        """Entity A has 0 customers, Entity B has 50 → 0 matches."""
        b_objects = [
            _obj(name=f"Vendor {i}", entity_source="eb")
            for i in range(50)
        ]
        result = run_prefilter([], b_objects)
        assert len(result.deterministic_matches) == 0
        assert len(result.ambiguous_remainder_a) == 0
        assert len(result.ambiguous_remainder_b) == 50

    def test_all_match(self):
        """Every object matches deterministically → empty remainder."""
        a_objs = [
            _obj(name="Acme", entity_source="ea"),
            _obj(name="Beta", entity_source="ea"),
        ]
        b_objs = [
            _obj(name="ACME INC", entity_source="eb"),
            _obj(name="Beta LLC", entity_source="eb"),
        ]
        result = run_prefilter(a_objs, b_objs)
        assert len(result.deterministic_matches) == 2
        assert len(result.ambiguous_remainder_a) == 0
        assert len(result.ambiguous_remainder_b) == 0

    def test_null_attributes(self):
        """Objects with null tax_id, domain, duns → only name comparison."""
        result = run_prefilter(
            [_obj(name="Acme", entity_source="ea")],
            [_obj(name="ACME INC", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        assert m.match_signal == "name"

    def test_objects_with_only_nulls(self):
        """Object with null everything except name → still compared by name."""
        a = _obj(
            name="Acme",
            entity_source="ea",
            tax_id=None,
            duns=None,
            domain=None,
        )
        b = _obj(
            name="ACME CORP",
            entity_source="eb",
            tax_id=None,
            duns=None,
            domain=None,
        )
        result = run_prefilter([a], [b])
        assert len(result.deterministic_matches) == 1
        assert result.deterministic_matches[0].match_signal == "name"

    def test_corroborating_attributes_populated(self):
        """When name matches and domain also matches, domain is listed as corroborating."""
        result = run_prefilter(
            [_obj(name="Acme Inc", domain="acme.com", tax_id="123", entity_source="ea")],
            [_obj(name="ACME Corp", domain="www.acme.com", tax_id="1-2-3", entity_source="eb")],
        )
        assert len(result.deterministic_matches) == 1
        m = result.deterministic_matches[0]
        # tax_id is highest priority so it's the signal
        assert m.match_signal == "tax_id"
        # name and domain should be corroborating
        assert "name" in m.corroborating_attributes
        assert "domain" in m.corroborating_attributes

    def test_matched_b_not_reused(self):
        """Once a B object is matched, it cannot be matched again by another A object."""
        result = run_prefilter(
            [
                _obj(name="Acme", entity_source="ea", object_id="a1"),
                _obj(name="Acme", entity_source="ea", object_id="a2"),
            ],
            [_obj(name="ACME INC", entity_source="eb", object_id="b1")],
        )
        # Only one A matches — the other goes to remainder
        assert len(result.deterministic_matches) == 1
        assert len(result.ambiguous_remainder_a) == 1
        assert len(result.ambiguous_remainder_b) == 0
