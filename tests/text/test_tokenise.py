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
