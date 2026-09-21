import pytest

from cvr.text import tokenise


def test_edge_punctuation_is_stripped_and_lone_dash_vanishes():
    assert tokenise("Software Engineer, Acme Ltd, 2019 - 2022") == [
        "Software",
        "Engineer",
        "Acme",
        "Ltd",
        "2019",
        "2022",
    ]


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("Engineer,", "Engineer"),
        ("(advanced)", "advanced"),
        ('"quoted"', "quoted"),
        ("C++", "C++"),
        ("O'Flynn", "O'Flynn"),
        ("O\u2019Flynn", "O'Flynn"),
        ("node.js", "node.js"),
        ("2019-2022", "2019-2022"),
        ("2019\u20132022", "2019-2022"),
        ("\u20ac50k", "\u20ac50k"),
    ],
)
def test_punctuation_is_stripped_from_edges_only(token, expected):
    assert tokenise(token) == [expected]


@pytest.mark.parametrize("glyph", ["\u2022", "-", "\u2013", "*", "\u2026"])
def test_lone_bullet_glyph_vanishes(glyph):
    assert tokenise(f"{glyph} Led the team") == ["Led", "the", "team"]


def test_case_and_typos_are_untouched():
    assert tokenise("Sofware ENGINEER at Acme") == ["Sofware", "ENGINEER", "at", "Acme"]


def test_empty_text_gives_no_tokens():
    assert tokenise("   \u200b ") == []


def test_symbols_on_a_token_edge_are_stripped_when_they_are_punctuation():
    """Pins the tokeniser on c07's skills: `C#` loses its hash and `.NET` its
    dot, because `#` and `.` are Unicode punctuation on a token edge, while
    `C++` survives because `+` is a symbol.

    This is a known limitation, not a target: `C` and `NET` are what the
    eval compares. The eval tolerates it because both sides of every
    comparison (the source document and the rendered output) tokenise
    alike, so the same token comes out of both and no add or drop is
    reported. Pinned here so the fact is a unit test and not a side-effect
    of regenerating the golden set.
    """
    assert tokenise("C#") == ["C"]
    assert tokenise(".NET") == ["NET"]
    assert tokenise("C++") == ["C++"]
    assert tokenise("Java, C#, .NET, C++") == ["Java", "C", "NET", "C++"]
