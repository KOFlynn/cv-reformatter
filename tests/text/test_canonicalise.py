import pytest

from cvr.text import CONFUSABLES, canonicalise

# One row per confusable, written out by hand so the test cannot pass by
# construction. Format: (name, source character, expected replacement).
CONFUSABLE_CASES = [
    # single quotes and single guillemets -> '
    ("left single quote", "\u2018", "'"),
    ("right single quote", "\u2019", "'"),
    ("single low-9 quote", "\u201a", "'"),
    ("single high-reversed-9 quote", "\u201b", "'"),
    ("single left guillemet", "\u2039", "'"),
    ("single right guillemet", "\u203a", "'"),
    # double quotes and double guillemets -> "
    ("left double quote", "\u201c", '"'),
    ("right double quote", "\u201d", '"'),
    ("double low-9 quote", "\u201e", '"'),
    ("double high-reversed-9 quote", "\u201f", '"'),
    ("left guillemet", "\u00ab", '"'),
    ("right guillemet", "\u00bb", '"'),
    # dashes -> -
    ("en dash", "\u2013", "-"),
    ("em dash", "\u2014", "-"),
    ("figure dash", "\u2012", "-"),
    ("non-breaking hyphen", "\u2011", "-"),
    ("minus sign", "\u2212", "-"),
    # ellipsis -> ...
    ("horizontal ellipsis", "\u2026", "..."),
    # exotic spaces -> space
    ("no-break space", "\u00a0", " "),
    ("narrow no-break space", "\u202f", " "),
    ("thin space", "\u2009", " "),
    ("hair space", "\u200a", " "),
    ("ideographic space", "\u3000", " "),
    # invisibles -> removed
    ("zero width space", "\u200b", ""),
    ("zero width non-joiner", "\u200c", ""),
    ("zero width joiner", "\u200d", ""),
    ("soft hyphen", "\u00ad", ""),
    ("byte order mark", "\ufeff", ""),
    ("word joiner", "\u2060", ""),
]


@pytest.mark.parametrize(
    ("source", "expected"),
    [(source, expected) for _, source, expected in CONFUSABLE_CASES],
    ids=[name for name, _, _ in CONFUSABLE_CASES],
)
def test_confusable_is_mapped_inside_a_word(source, expected):
    assert canonicalise(f"a{source}b") == f"a{expected}b"


def test_every_table_row_has_a_case():
    assert set(CONFUSABLES) == {source for _, source, _ in CONFUSABLE_CASES}


def test_nfc_composes_decomposed_fada():
    # 'a' followed by a combining acute accent composes to the precomposed a-fada.
    assert canonicalise("Sea\u0301n") == "Se\u00e1n"


def test_whitespace_is_collapsed_and_trimmed():
    assert canonicalise("  Software \t Engineer\n\nAcme ") == "Software Engineer Acme"


def test_exotic_space_collapses_with_neighbouring_whitespace():
    assert canonicalise("2019 \u00a0 2022") == "2019 2022"


@pytest.mark.parametrize(
    "compatibility_char", ["\u00bd", "\u2122"], ids=["one-half", "trademark"]
)
def test_compatibility_characters_are_not_rewritten(compatibility_char):
    # NFC, not NFKC: NFKC would turn one-half into 1/2 and the trademark sign into TM.
    assert canonicalise(compatibility_char) == compatibility_char


def test_case_and_typos_are_untouched():
    assert canonicalise("Sofware ENGINEER") == "Sofware ENGINEER"
