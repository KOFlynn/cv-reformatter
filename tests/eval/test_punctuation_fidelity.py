"""The guard on provenance's blind spot (ADR-0007): the raw located span
against the raw rendered unit, byte for byte, no canonicalisation. A
reported metric until the Phase 1 baseline shows it clean."""

from cvr.eval import Finding, punctuation_fidelity


def test_identical_pairs_have_no_findings():
    pairs = [("O\u2019Sampla", "O\u2019Sampla"), ("Led the team", "Led the team")]
    assert punctuation_fidelity(pairs) == []


def test_a_straightened_apostrophe_is_a_finding_naming_the_unit_and_the_character():
    # provenance_violations cannot see this: both sides canonicalise to the
    # same string. Fidelity reads the raw text and names the character.
    pairs = [("O\u2019Sampla", "O'Sampla")]
    assert punctuation_fidelity(pairs) == [
        Finding(what="\u2019 (U+2019) -> ' (U+0027)", count=1, where="O'Sampla")
    ]


def test_no_normalisation_at_all_so_a_decomposed_accent_is_a_finding():
    # NFC would make these equal; every other metric applies it, this one
    # must not, or a renderer recomposing text would go unnoticed.
    composed = "Sin\u00e9ad"
    decomposed = "Sine\u0301ad"
    assert punctuation_fidelity([(composed, decomposed)]) == [
        Finding(what="\u00e9 (U+00E9) -> e (U+0065)", count=1, where=decomposed)
    ]


def test_a_unit_that_stops_short_names_the_end_of_text():
    assert punctuation_fidelity([("Led the team.", "Led the team")]) == [
        Finding(what=". (U+002E) -> (end)", count=1, where="Led the team")
    ]


def test_a_unit_that_runs_on_names_the_end_of_the_span():
    assert punctuation_fidelity([("Led the team", "Led the team ")]) == [
        Finding(what="(end) ->   (U+0020)", count=1, where="Led the team ")
    ]


def test_the_same_difference_in_the_same_unit_twice_is_one_finding_of_two():
    pairs = [("O\u2019Sampla", "O'Sampla")] * 2
    assert punctuation_fidelity(pairs) == [
        Finding(what="\u2019 (U+2019) -> ' (U+0027)", count=2, where="O'Sampla")
    ]


def test_empty_input_gives_no_findings():
    assert punctuation_fidelity([]) == []


def test_findings_are_sorted_by_unit_then_difference():
    pairs = [
        ("zeta\u2019", "zeta'"),
        ("alpha\u2013beta", "alpha-beta"),
        ("alpha\u2019", "alpha'"),
    ]
    assert punctuation_fidelity(pairs) == [
        Finding(what="\u2019 (U+2019) -> ' (U+0027)", count=1, where="alpha'"),
        Finding(what="\u2013 (U+2013) -> - (U+002D)", count=1, where="alpha-beta"),
        Finding(what="\u2019 (U+2019) -> ' (U+0027)", count=1, where="zeta'"),
    ]
