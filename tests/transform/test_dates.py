"""Date normalisation: one fragment (``parse_date``) and a whole range block
(``split_dates``)."""

import pytest

from cvr.models import Span
from cvr.transform.dates import parse_date, split_dates

# --- parse_date: every accepted format, straight and curly apostrophe alike.

ACCEPTED = [
    ("Jan 2020", "01/2020"),
    ("January 2020", "01/2020"),
    ("01/2020", "01/2020"),
    ("1/2020", "01/2020"),
    ("2020-01", "01/2020"),
    ("Jan '20", "01/2020"),
    ("2020", "2020"),
    ("Present", "Present"),
    ("Current", "Present"),
    ("to date", "Present"),
    ("now", "Present"),
    ("PRESENT", "Present"),  # case-folded
]


@pytest.mark.parametrize(("text", "expected"), ACCEPTED)
def test_accepted_format(text: str, expected: str) -> None:
    date = parse_date(text)
    assert date.value == expected
    assert date.literal is False


def test_curly_apostrophe_matches_straight() -> None:
    straight = parse_date("Jan '20")
    curly = parse_date("Jan ’20")
    assert straight.value == curly.value == "01/2020"


@pytest.mark.parametrize(
    "text", [text for text, expected in ACCEPTED if "'" in text or "’" in text]
)
def test_every_apostrophe_format_has_a_curly_twin(text: str) -> None:
    curly = text.replace("'", "’")
    assert parse_date(text).value == parse_date(curly).value


# --- literals: verbatim, sorted by first four-digit year, else undated.


def test_literal_is_verbatim() -> None:
    date = parse_date("Summer 2020")
    assert date.literal is True
    assert date.value == "Summer 2020"
    assert date.year == 2020


def test_literal_with_no_year_is_undated() -> None:
    date = parse_date("a while ago")
    assert date.literal is True
    assert date.year is None


def test_literal_never_invents_a_month() -> None:
    date = parse_date("Summer 2020")
    assert date.month is None


# --- split_dates: whole-as-single tried first, then split on a separator.


def _span(text: str) -> Span:
    return Span(block_id="body:0", start=100, end=100 + len(text), text=text)


def test_lone_date_is_not_a_range() -> None:
    split = split_dates(_span("2020-01"))
    assert split.start is None
    assert split.end is not None
    assert split.end.value == "01/2020"


@pytest.mark.parametrize(
    "text",
    [
        "January 2020 - June 2026",
        "01/2020 – 06/2026",  # en dash, the two-column Layout's style
        "2022-03 to 2026-07",
    ],
)
def test_range_styles_split_correctly(text: str) -> None:
    split = split_dates(_span(text))
    assert split.start is not None
    assert split.end is not None
    assert split.start.literal is False
    assert split.end.literal is False


def test_hyphen_range_with_spaces_splits() -> None:
    split = split_dates(_span("2020-01 - 2021-06"))
    assert split.start is not None and split.start.value == "01/2020"
    assert split.end is not None and split.end.value == "06/2021"


def test_em_dash_range_splits() -> None:
    split = split_dates(_span("Jan 2020 — Dec 2020"))
    assert split.start is not None and split.start.value == "01/2020"
    assert split.end is not None and split.end.value == "12/2020"


def test_range_date_map_has_one_pair_per_side() -> None:
    span = _span("2020-01 - 2021-06")
    split = split_dates(span)
    assert set(split.date_map) == {"01/2020", "06/2021"}
    for slice_ in split.date_map.values():
        assert slice_.block_id == span.block_id
        assert (
            span.text[slice_.start - span.start : slice_.end - span.start]
            == slice_.text
        )


def test_single_date_map_is_the_whole_span() -> None:
    span = _span("2020-01")
    split = split_dates(span)
    assert split.date_map == {"01/2020": span}


def test_a_date_inside_body_text_is_never_touched() -> None:
    """``split_dates``/``parse_date`` only ever see what ``transform``
    routes to them: an entry's ``dates`` reference. A certification's
    string never reaches this module at all, so "renewed March 2024" stays
    exactly as printed; see ``test_transform.py`` for the content-tree proof."""
    date = parse_date("renewed March 2024")
    # not one of the accepted formats: passed through untouched, as a literal
    assert date.literal is True
    assert date.value == "renewed March 2024"
