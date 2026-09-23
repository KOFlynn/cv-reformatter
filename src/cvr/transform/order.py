"""Entry order: end date descending with Present first, then start date
descending, then source order.

One rank function serves both keys and both entry kinds (experience,
education): Present ranks above every real date, a real date ranks by
``(year, month)`` with a year-only date read as January of that year (for
ordering only; it is never printed with a month), and no date (or a literal
with no extractable year) ranks last and falls back to source order.

Depends on ``cvr.transform.dates`` only. No LLM, no clock, no network.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from cvr.transform.dates import NormalisedDate

__all__ = ["Ranked", "order"]

# Rank tiers, highest first: Present, a date with a year, nothing sortable.
_PRESENT, _DATED, _UNDATED = 2, 1, 0


@dataclass(frozen=True, slots=True)
class Ranked[T]:
    """One entry with the dates ``order`` needs and nothing else: the built
    item, its start and end dates, and its position in source order."""

    item: T
    start: NormalisedDate | None
    end: NormalisedDate | None
    index: int


def _rank(date: NormalisedDate | None) -> tuple[int, int, int]:
    if date is None or date.year is None and not date.present:
        return (_UNDATED, 0, 0)
    if date.present:
        return (_PRESENT, 0, 0)
    return (_DATED, date.year, date.month or 1)


def _key(ranked: Ranked) -> tuple[int, ...]:
    end_tier, end_year, end_month = _rank(ranked.end)
    start_tier, start_year, start_month = _rank(ranked.start)
    return (
        -end_tier,
        -end_year,
        -end_month,
        -start_tier,
        -start_year,
        -start_month,
        ranked.index,
    )


def order[T](items: Iterable[Ranked[T]]) -> list[T]:
    """``items`` in entry order: end date descending (Present first), then
    start date descending, then source order."""
    return [ranked.item for ranked in sorted(items, key=_key)]
