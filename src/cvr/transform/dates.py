"""Entry-date normalisation: one date, and the whole range block it may sit
inside.

``parse_date`` classifies one fragment of text: the present-family words, one
of the accepted numeric or month-name formats, or (failing all of those) a
literal passed through verbatim, sorted by the first four-digit year it
contains. ``split_dates`` decides whether a range block's ``Span`` is a
single date or two, trying the whole text as one date first and splitting on
a range separator only when that fails, so ``2020-01`` (a date, hyphen with
no spaces) is never confused with ``2020-01 - 2021-06`` (a range, spaced
dashes and en/em dashes alike, since ``canonicalise`` maps every dash
variant onto ``-`` before the range separator is even looked for).

Depends on ``cvr.models`` and ``cvr.text`` only. No LLM, no clock, no
network: every function here is a pure function of the text it is given.
"""

import re
from dataclasses import dataclass

from cvr.models import Span
from cvr.text import canonicalise, canonicalise_with_offsets

__all__ = ["DateSplit", "NormalisedDate", "parse_date", "split_dates"]

_PRESENT_WORDS = frozenset({"present", "current", "to date", "now"})

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# "Jan 2020", "January 2020", "Jan '20" (curly or straight apostrophe alike,
# since canonicalise straightens it first).
_MONTH_YEAR = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?:'(?P<yy>\d{2})|(?P<yyyy>\d{4}))$")
_SLASH = re.compile(r"^(?P<month>\d{1,2})/(?P<year>\d{4})$")  # "01/2020", "1/2020"
_ISO = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{1,2})$")  # "2020-01"
_YEAR_ONLY = re.compile(r"^(?P<year>\d{4})$")  # "2020"
_YEAR_RUN = re.compile(r"\d{4}")

# Every dash variant canonicalises to "-", so this one pattern catches
# " - ", " – " and " — " alike; " to " is its own word.
_RANGE_SEPARATOR = re.compile(r" - | to ")


@dataclass(frozen=True, slots=True)
class NormalisedDate:
    """One entry date after classification.

    ``value`` is the printed form: ``MM/YYYY``, ``YYYY``, ``Present``, or
    (when ``literal`` is set) the original text verbatim. ``year``/``month``
    are for entry-order comparison only, never for re-deriving ``value``.
    """

    value: str
    year: int | None
    month: int | None
    present: bool
    literal: bool


@dataclass(frozen=True, slots=True)
class DateSplit:
    """The result of splitting one range block: ``start`` is ``None`` for a
    block holding a single date (assigned to ``end``; see the ticket 04
    comments for why). ``date_map`` holds one pair per normalised value that
    could be traced back to a contiguous raw slice."""

    start: NormalisedDate | None
    end: NormalisedDate | None
    date_map: dict[str, Span]


def _classify(canonical: str) -> tuple[int | None, int] | None:
    """``(month, year)`` for a canonicalised fragment that matches one of the
    accepted formats, ``month`` ``None`` for a year-only match; ``None`` when
    nothing matches."""
    if match := _MONTH_YEAR.match(canonical):
        month = _MONTHS.get(match["month"].casefold())
        if month is None:
            return None
        year = int(match["yyyy"]) if match["yyyy"] else 2000 + int(match["yy"])
        return month, year
    if match := _SLASH.match(canonical):
        month = int(match["month"])
        return (month, int(match["year"])) if 1 <= month <= 12 else None
    if match := _ISO.match(canonical):
        month = int(match["month"])
        return (month, int(match["year"])) if 1 <= month <= 12 else None
    if match := _YEAR_ONLY.match(canonical):
        return None, int(match["year"])
    return None


def _first_year(text: str) -> int | None:
    match = _YEAR_RUN.search(text)
    return int(match.group()) if match else None


def parse_date(text: str) -> NormalisedDate:
    """Classify one date fragment. Present-family words, then the accepted
    formats, then a verbatim literal sorted by its first four-digit year."""
    canonical = canonicalise(text)
    if canonical.casefold() in _PRESENT_WORDS:
        return NormalisedDate(
            value="Present", year=None, month=None, present=True, literal=False
        )
    classified = _classify(canonical)
    if classified is not None:
        month, year = classified
        if month is None:
            return NormalisedDate(
                value=f"{year:04d}", year=year, month=None, present=False, literal=False
            )
        return NormalisedDate(
            value=f"{month:02d}/{year:04d}",
            year=year,
            month=month,
            present=False,
            literal=False,
        )
    return NormalisedDate(
        value=text, year=_first_year(canonical), month=None, present=False, literal=True
    )


def _sub_span(
    span: Span, offsets: tuple[int, ...], ends: tuple[int, ...], i: int, j: int
) -> Span | None:
    """The ``Span`` behind canonical ``[i, j)`` of ``span``'s own text, or
    ``None`` when the range is empty."""
    if i >= j:
        return None
    local_start, local_end = offsets[i], ends[j - 1]
    if local_start >= local_end:
        return None
    return Span(
        block_id=span.block_id,
        start=span.start + local_start,
        end=span.start + local_end,
        text=span.text[local_start:local_end],
    )


def split_dates(span: Span) -> DateSplit:
    """Split one range block's ``Span``: the whole text tried as a single
    date first, then split on a range separator, else a literal."""
    whole = parse_date(span.text)
    if not whole.literal:
        return DateSplit(start=None, end=whole, date_map={whole.value: span})

    canonical = canonicalise_with_offsets(span.text)
    match = _RANGE_SEPARATOR.search(canonical.text)
    if match is None:
        return DateSplit(start=None, end=whole, date_map={whole.value: span})

    left = _sub_span(span, canonical.offsets, canonical.ends, 0, match.start())
    right = _sub_span(
        span, canonical.offsets, canonical.ends, match.end(), len(canonical.text)
    )
    start_date = parse_date(left.text) if left is not None else None
    end_date = parse_date(right.text) if right is not None else None
    date_map: dict[str, Span] = {}
    if left is not None and start_date is not None:
        date_map[start_date.value] = left
    if right is not None and end_date is not None:
        date_map[end_date.value] = right
    return DateSplit(start=start_date, end=end_date, date_map=date_map)
