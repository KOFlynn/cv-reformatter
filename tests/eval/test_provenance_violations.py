"""The primary invariant check (ADR-0007): every rendered unit is an exact
canonicalised substring of some source block, a template unit, or the
rendered side of a date-map pair. Whole units, not bags of words."""

from cvr.eval import Finding, provenance_violations

BLOCKS = ["Led the team", "of five engineers, remotely", "Python"]
TEMPLATE = ["Experience", "Key Skills", ","]


def test_a_unit_that_is_a_slice_of_one_block_is_not_a_violation():
    units = ["Led the team", "five engineers", "Python"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, []) == []


def test_a_unit_spanning_two_blocks_is_a_violation():
    # Every word has provenance; the unit does not. This is exactly what a
    # bag-of-words check cannot see.
    units = ["Led the team of five engineers, remotely"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, []) == [
        Finding(
            what="Led the team of five engineers, remotely", count=1, where="output"
        )
    ]


def test_a_template_heading_as_a_whole_unit_is_not_a_violation():
    assert provenance_violations(["Experience", ","], BLOCKS, TEMPLATE, []) == []


def test_a_template_word_used_as_filler_inside_a_bullet_is_a_violation():
    # Every token is whitelisted (template_tokens permits "Experience"
    # anywhere), so added_tokens passes; provenance checks the whole unit
    # against whole blocks and whole template units, and closes that hole.
    units = ["Led the Experience team"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, []) == [
        Finding(what="Led the Experience team", count=1, where="output")
    ]


def test_a_fragment_of_a_template_unit_is_a_violation():
    assert provenance_violations(["Key"], BLOCKS, TEMPLATE, []) == [
        Finding(what="Key", count=1, where="output")
    ]


def test_the_rendered_side_of_a_mapped_date_is_not_a_violation():
    date_map = [("March 2022", "03/2022"), ("Summer 2020", "Summer 2020")]
    units = ["03/2022", "Summer 2020"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, date_map) == []


def test_the_source_side_of_a_mapped_date_is_not_permitted_by_the_map():
    date_map = [("March 2022", "03/2022")]
    assert provenance_violations(["March 2022"], BLOCKS, TEMPLATE, date_map) == [
        Finding(what="March 2022", count=1, where="output")
    ]


def test_the_match_is_canonicalised_on_both_sides():
    # A straightened apostrophe and collapsed whitespace still have
    # provenance here; noticing them is punctuation_fidelity's job.
    blocks = ["O\u2019Sampla\u00a0led  the\u2013team"]
    units = ["O'Sampla led the-team"]
    assert provenance_violations(units, blocks, [], []) == []


def test_a_unit_that_renders_nothing_is_skipped():
    assert provenance_violations(["", "  ", "\u200b"], [], [], []) == []


def test_empty_inputs_give_no_findings():
    assert provenance_violations([], [], [], []) == []


def test_the_same_violation_twice_is_one_finding_of_two():
    units = ["invented", "invented"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, []) == [
        Finding(what="invented", count=2, where="output")
    ]


def test_findings_are_sorted_by_unit_as_rendered():
    units = ["zeta", "alpha", "Mid"]
    assert provenance_violations(units, BLOCKS, TEMPLATE, []) == [
        Finding(what="Mid", count=1, where="output"),
        Finding(what="alpha", count=1, where="output"),
        Finding(what="zeta", count=1, where="output"),
    ]
