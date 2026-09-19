import pytest

from cvr.text import SEPARATORS, is_separator_residue


def test_run_of_list_punctuation_and_whitespace_is_separator_residue():
    # What is left between two placed skills once both are claimed.
    assert is_separator_residue(", ")
    assert is_separator_residue(" ; / ")


def test_ampersand_alone_is_not_separator_residue():
    # `&` is a content token, not decoration: it is a word in "M&S" and in
    # "Research & Development", so a stray `&` is unplaced text that must
    # reach the appendix rather than be dropped as a separator.
    assert "&" not in SEPARATORS
    assert not is_separator_residue("&")
    assert not is_separator_residue(" & ")


@pytest.mark.parametrize(
    "bullet",
    ["\uf0b7", "\uf0a7", "\uf0d8", "\uf0fc", "\uf076"],
    ids=["F0B7", "F0A7", "F0D8", "F0FC", "F076"],
)
def test_symbol_font_private_use_area_bullet_is_separator_residue(bullet):
    # Word writes its Symbol-font bullets into the Private Use Area; no
    # golden document carries one in paragraph text, so they are pinned here.
    assert bullet in SEPARATORS
    assert is_separator_residue(bullet)
    assert is_separator_residue(f"{bullet} ")


@pytest.mark.parametrize(
    "glyph", ["\u2022", "\u00b7", "\u25e6", "\u25aa", "\u2023", "\u25cb", "\u25a0"]
)
def test_bullet_glyph_is_separator_residue(glyph):
    assert is_separator_residue(glyph)


@pytest.mark.parametrize("dash", ["-", "\u2013", "\u2014"])
def test_dash_is_separator_residue(dash):
    assert is_separator_residue(f" {dash} ")


@pytest.mark.parametrize("quote", ["'", '"', "\u2018", "\u2019", "\u201c", "\u201d"])
def test_straight_and_curly_quote_is_separator_residue(quote):
    assert is_separator_residue(quote)


@pytest.mark.parametrize("text", ["2:1", "Languages:", "a", "\u00bd"])
def test_text_with_a_non_separator_is_not_separator_residue(text):
    # The colon is a separator; the digits and letters around it are not.
    assert not is_separator_residue(text)


def test_every_separator_is_a_single_character():
    assert all(len(separator) == 1 for separator in SEPARATORS)
