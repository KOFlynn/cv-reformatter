import pytest
from docx_text import all_text

from cvr.golden.generate import GENERATED_DIR
from cvr.text import Canonical, canonicalise, canonicalise_with_offsets

# One case per row class of the confusable table, plus NFC composition and
# whitespace collapse: (name, raw, expected canonical, expected offsets,
# expected ends). Written out by hand so the test cannot pass by construction.
OFFSET_CASES = [
    # one-to-one substitution: the canonical quote sits where the curly one was
    (
        "curly quote",
        "O\u2019Flynn",
        "O'Flynn",
        [0, 1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6, 7],
    ),
    ("curly double quote", "a\u201cb", 'a"b', [0, 1, 2], [1, 2, 3]),
    ("en dash", "1\u20132", "1-2", [0, 1, 2], [1, 2, 3]),
    # one-to-zero deletion: the invisible leaves no canonical character
    ("zero width space", "a\u200bb", "ab", [0, 2], [1, 3]),
    # exotic space to space: a substitution, then treated as whitespace
    ("no-break space", "a\u00a0b", "a b", [0, 1, 2], [1, 2, 3]),
    # many-to-one: a run of whitespace collapses onto its first character and
    # its end covers the whole run
    ("run of spaces", "a \t\n b", "a b", [0, 1, 5], [1, 5, 6]),
    # an invisible inside a run of whitespace does not split the run
    ("invisible in a run", "a \u200b b", "a b", [0, 1, 4], [1, 4, 5]),
    # leading and trailing whitespace is trimmed, so the map starts inside
    ("trim", "  ab ", "ab", [2, 3], [3, 4]),
    # one-to-many: the ellipsis expands to three dots sharing one raw range
    ("ellipsis", "a\u2026b", "a...b", [0, 1, 1, 1, 2], [1, 2, 2, 2, 3]),
    # NFC: a base letter and its combining mark compose onto the base's range
    ("decomposed fada", "Sea\u0301n", "Se\u00e1n", [0, 1, 2, 4], [1, 2, 4, 5]),
    # NFC across starters: Hangul jamo are all combining class zero yet
    # compose into one syllable, so the cut between them must not be made
    ("hangul jamo", "\u1100\u1161\u11a8", "\uac01", [0], [3]),
]


@pytest.mark.parametrize(
    ("raw", "expected_text", "expected_offsets", "expected_ends"),
    [case[1:] for case in OFFSET_CASES],
    ids=[case[0] for case in OFFSET_CASES],
)
def test_known_answer(raw, expected_text, expected_offsets, expected_ends):
    canonical = canonicalise_with_offsets(raw)
    assert canonical.raw == raw
    assert canonical.text == expected_text
    assert list(canonical.offsets) == expected_offsets
    assert list(canonical.ends) == expected_ends


def test_raw_slice_round_trips_a_mixed_string_byte_for_byte():
    # Every row class at once: composition, a curly quote, a deletion, an
    # exotic space, a collapse and an ellipsis. Slicing the whole canonical
    # string gives back the raw string untouched.
    raw = "Sea\u0301n\u00a0O\u2019Flynn\u200b,  C++\u2026 done"
    canonical = canonicalise_with_offsets(raw)
    assert canonical.text == "Se\u00e1n O'Flynn, C++... done"
    assert canonical.raw_slice(0, len(canonical.text)) == raw


def test_raw_slice_of_a_canonical_match_keeps_the_raw_characters():
    # The verifier matches on canonical text and slices raw: the curly quote
    # and the decomposed fada come back as the source wrote them.
    raw = "Name:  Sea\u0301n O\u2019Flynn (he/him)"
    canonical = canonicalise_with_offsets(raw)
    start = canonical.text.index("Se\u00e1n O'Flynn")
    end = start + len("Se\u00e1n O'Flynn")
    assert canonical.raw_slice(start, end) == "Sea\u0301n O\u2019Flynn"


def test_raw_slice_ending_on_a_collapsed_run_takes_the_whole_run():
    canonical = canonicalise_with_offsets("a \t b")
    assert canonical.raw_slice(0, 2) == "a \t "


def test_raw_slice_ending_inside_an_ellipsis_takes_the_whole_glyph():
    # The three dots share one raw character, so a slice cannot stop between
    # them: it either excludes the glyph or takes all of it.
    canonical = canonicalise_with_offsets("wait\u2026 more")
    assert canonical.raw_slice(0, 4) == "wait"
    assert canonical.raw_slice(0, 5) == "wait\u2026"
    assert canonical.raw_slice(0, 7) == "wait\u2026"


@pytest.mark.parametrize("raw", ["", "  \u200b\t"], ids=["empty", "whitespace only"])
def test_text_with_nothing_to_keep_gives_an_empty_map(raw):
    canonical = canonicalise_with_offsets(raw)
    assert canonical == Canonical(raw=raw, text="", offsets=(), ends=())
    assert canonical.raw_slice(0, 0) == ""


@pytest.mark.slow
@pytest.mark.parametrize("document", sorted(GENERATED_DIR.glob("*.docx")))
def test_agrees_with_canonicalise_over_the_golden_set(document):
    # Property-style: every text run of every generated document, traps and
    # all, canonicalises to the same string by both routes and slices back
    # to its raw self (less the whitespace canonicalise trims).
    for raw in all_text(document):
        canonical = canonicalise_with_offsets(raw)
        assert canonical.text == canonicalise(raw)
        assert len(canonical.offsets) == len(canonical.text)
        assert canonical.raw_slice(0, len(canonical.text)) == _trimmed(raw)


def _trimmed(raw: str) -> str:
    # What the whole-string slice should give back: `raw` less the leading
    # and trailing characters that canonicalise to nothing (whitespace and
    # invisibles), which the map never covers. `str.strip` takes the set of
    # characters to remove from both ends, so it is handed exactly those.
    dropped = "".join(char for char in raw if canonicalise(char) == "")
    return raw.strip(dropped)
