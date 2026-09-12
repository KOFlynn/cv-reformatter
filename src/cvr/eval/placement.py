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
from enum import StrEnum

from cvr.eval.alignment import (
    AlignedBy,
    Alignment,
    Entry,
    Section,
    align,
    section_entries,
)
from cvr.models import CVContent, DateValue
from cvr.text import canonicalise

__all__ = ["FieldType", "PlacementReport", "Tally", "placement_accuracy"]


class FieldType(StrEnum):
    """Every kind of leaf, structural ones first.

    Structural leaves identify an entry or the candidate and gate at 100%;
    the rest are free text on the tunable threshold. Start and end dates are
    one type: a date is a date wherever it sits.
    """

    NAME = "name"
    TITLE = "title"
    EMPLOYER = "employer"
    LOCATION = "location"
    DATE = "date"
    INSTITUTION = "institution"
    QUALIFICATION = "qualification"
    PROFILE = "profile"
    SKILL = "skill"
    BULLET = "bullet"
    DETAIL = "detail"
    CERTIFICATION = "certification"
    ADDITIONAL = "additional"

    @property
    def structural(self) -> bool:
        return self in _STRUCTURAL


_STRUCTURAL = frozenset(
    {
        FieldType.NAME,
        FieldType.TITLE,
        FieldType.EMPLOYER,
        FieldType.LOCATION,
        FieldType.DATE,
        FieldType.INSTITUTION,
        FieldType.QUALIFICATION,
    }
)


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


def _canon(texts: Iterable[str]) -> Counter[str]:
    return Counter(canonicalise(text) for text in texts)


def _scalar(actual: str | None, expected: str | None) -> Tally:
    # An optional scalar present on one side only is a miss on that side alone.
    if actual is None and expected is None:
        return Tally()
    if actual is None or expected is None:
        return Tally(0, int(actual is not None), int(expected is not None))
    return Tally(int(canonicalise(actual) == canonicalise(expected)), 1, 1)


def _date(actual: DateValue | None, expected: DateValue | None) -> Tally:
    return _scalar(
        None if actual is None else actual.expected,
        None if expected is None else expected.expected,
    )


def _list(actual: Iterable[str], expected: Iterable[str]) -> Tally:
    a, e = _canon(actual), _canon(expected)
    return Tally(sum((a & e).values()), sum(a.values()), sum(e.values()))


def _get(entry: object | None, name: str, absent: object = None) -> object:
    return absent if entry is None else getattr(entry, name)


def _entry_leaves(
    section: Section, actual: Entry | None, expected: Entry | None
) -> dict[FieldType, Tally]:
    """Field-by-field tallies for a pair. An unmatched entry is compared
    against nothing: every scalar absent, every list empty, so each of its
    leaves misses on its own side only."""
    a, e = actual, expected
    dates = _date(_get(a, "start"), _get(e, "start")) + _date(
        _get(a, "end"), _get(e, "end")
    )
    if section is Section.EXPERIENCE:
        return {
            FieldType.TITLE: _scalar(_get(a, "title"), _get(e, "title")),
            FieldType.EMPLOYER: _scalar(_get(a, "employer"), _get(e, "employer")),
            FieldType.LOCATION: _scalar(_get(a, "location"), _get(e, "location")),
            FieldType.DATE: dates,
            FieldType.BULLET: _list(_get(a, "bullets", []), _get(e, "bullets", [])),
        }
    return {
        FieldType.INSTITUTION: _scalar(_get(a, "institution"), _get(e, "institution")),
        FieldType.QUALIFICATION: _scalar(
            _get(a, "qualification"), _get(e, "qualification")
        ),
        FieldType.DATE: dates,
        FieldType.DETAIL: _list(_get(a, "details", []), _get(e, "details", [])),
    }


def placement_accuracy(actual: CVContent, expected: CVContent) -> PlacementReport:
    by_field = {field: Tally() for field in FieldType}
    by_field[FieldType.NAME] = _scalar(actual.name, expected.name)
    by_field[FieldType.PROFILE] = _list(actual.profile, expected.profile)
    by_field[FieldType.SKILL] = _list(actual.skills, expected.skills)
    by_field[FieldType.CERTIFICATION] = _list(
        actual.certifications, expected.certifications
    )
    by_field[FieldType.ADDITIONAL] = _list(actual.additional, expected.additional)

    alignments = align(actual, expected)
    for section, section_alignments in alignments.items():
        a_entries = section_entries(actual, section)
        e_entries = section_entries(expected, section)
        for alignment in section_alignments:
            a = None if alignment.actual is None else a_entries[alignment.actual]
            e = None if alignment.expected is None else e_entries[alignment.expected]
            for field, tally in _entry_leaves(section, a, e).items():
                by_field[field] += tally

    return PlacementReport(
        by_field, tuple(a for section in Section for a in alignments[section])
    )
