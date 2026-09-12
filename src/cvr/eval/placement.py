"""Placement accuracy: did each piece of content land in the right field?

Entries are aligned first (``cvr.eval.alignment``), so one wrong employer is
one wrong leaf rather than a whole entry's worth. Within an aligned pair,
scalar leaves compare field to field and list leaves as a multiset of
canonicalised text; both sides of every comparison are canonicalised, as in
every other metric. Precision counts the actual side (what was placed, how
much of it belongs) and recall the expected side (what should be there, how
much was found); the two are reported separately and never combined.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import zip_longest

from cvr.eval.alignment import AlignedBy, Alignment, Section, align, section_entries
from cvr.eval.leaves import FieldType, Leaves, content_leaves, entry_leaves
from cvr.models import CVContent
from cvr.text import canonicalise

__all__ = ["PlacementReport", "Tally", "placement_accuracy"]


@dataclass(frozen=True, slots=True)
class Tally:
    """Leaf counts for one field type, or summed over several.

    ``hits`` leaves matched, out of ``actual`` placed and ``expected`` wanted.
    Nothing placed and nothing wanted is a perfect score, not a division error,
    so an empty section never drags a report down.
    """

    hits: int = 0
    actual: int = 0
    expected: int = 0

    @property
    def precision(self) -> float:
        return self.hits / self.actual if self.actual else 1.0

    @property
    def recall(self) -> float:
        return self.hits / self.expected if self.expected else 1.0

    def __add__(self, other: "Tally") -> "Tally":
        return Tally(
            self.hits + other.hits,
            self.actual + other.actual,
            self.expected + other.expected,
        )


@dataclass(frozen=True, slots=True)
class PlacementReport:
    """``by_field`` carries every ``FieldType``; ``alignments`` every entry of
    both contents (the ticket's ``aligned_by`` per entry)."""

    by_field: dict[FieldType, Tally]
    alignments: tuple[Alignment, ...]

    @property
    def overall(self) -> Tally:
        return sum(self.by_field.values(), Tally())

    @property
    def structural(self) -> Tally:
        return sum((t for f, t in self.by_field.items() if f.structural), Tally())

    @property
    def tunable(self) -> Tally:
        return sum((t for f, t in self.by_field.items() if not f.structural), Tally())

    @property
    def unaligned_entries(self) -> dict[Section, int]:
        """Entries on either side that no pass could pair, per section."""
        return {
            section: sum(
                1
                for a in self.alignments
                if a.section is section and a.aligned_by is AlignedBy.UNMATCHED
            )
            for section in Section
        }


def _scalar(actual: str | None, expected: str | None) -> Tally:
    # An optional scalar present on one side only is a miss on that side alone.
    if actual is None and expected is None:
        return Tally()
    if actual is None or expected is None:
        return Tally(0, int(actual is not None), int(expected is not None))
    return Tally(int(canonicalise(actual) == canonicalise(expected)), 1, 1)


def _list(actual: Iterable[str], expected: Iterable[str]) -> Tally:
    a = Counter(canonicalise(text) for text in actual)
    e = Counter(canonicalise(text) for text in expected)
    return Tally(sum((a & e).values()), sum(a.values()), sum(e.values()))


# The missing partner of an unmatched entry: no slots and no items, so every
# leaf on the other side misses on its own side only.
_NOTHING = Leaves({}, {})


def _tallies(actual: Leaves, expected: Leaves) -> dict[FieldType, Tally]:
    tallies: dict[FieldType, Tally] = {}
    for field in actual.scalars.keys() | expected.scalars.keys():
        slots = zip_longest(
            actual.scalars.get(field, ()), expected.scalars.get(field, ())
        )
        tallies[field] = sum((_scalar(a, e) for a, e in slots), Tally())
    for field in actual.lists.keys() | expected.lists.keys():
        tallies[field] = _list(
            actual.lists.get(field, ()), expected.lists.get(field, ())
        )
    return tallies


def placement_accuracy(actual: CVContent, expected: CVContent) -> PlacementReport:
    by_field = {field: Tally() for field in FieldType}
    for field, tally in _tallies(
        content_leaves(actual), content_leaves(expected)
    ).items():
        by_field[field] += tally

    alignments = align(actual, expected)
    for section, section_alignments in alignments.items():
        a_entries = section_entries(actual, section)
        e_entries = section_entries(expected, section)
        for alignment in section_alignments:
            a = (
                _NOTHING
                if alignment.actual is None
                else entry_leaves(a_entries[alignment.actual])
            )
            e = (
                _NOTHING
                if alignment.expected is None
                else entry_leaves(e_entries[alignment.expected])
            )
            for field, tally in _tallies(a, e).items():
                by_field[field] += tally

    return PlacementReport(
        by_field, tuple(a for section in Section for a in alignments[section])
    )
