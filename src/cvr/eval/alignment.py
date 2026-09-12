"""Entry alignment: which actual entry is which expected entry.

Both structural metrics need this before they can compare anything, and they
must agree on it, so it lives here once. Two passes per section. Pass one
matches on the alignment key: experience on canonicalised employer plus the
structured start date, education on canonicalised institution plus
qualification. Pass two pairs the remainder greedily by best Jaccard overlap
of canonicalised leaves, with a cutoff of 0.5. An entry unmatched after both
passes was lost; an entry matched on the fallback pass was found with a wrong
key. The two are never conflated.
"""

from dataclasses import dataclass
from enum import StrEnum

from cvr.models import CVContent, EducationEntry, ExperienceEntry
from cvr.text import canonicalise

__all__ = [
    "AlignedBy",
    "Alignment",
    "Entry",
    "Key",
    "Section",
    "align",
    "entry_key",
    "entry_leaves",
    "section_entries",
]

# Below this overlap two entries are different entries, not one entry with
# errors. Half: the point at which more of the entry is wrong than right.
FALLBACK_CUTOFF = 0.5

Entry = ExperienceEntry | EducationEntry
# Experience: (employer, (year, month)). Education: (institution, qualification).
Key = tuple[str, tuple[int | None, int | None]] | tuple[str, str]


class Section(StrEnum):
    """The two sections whose items are entries rather than plain strings."""

    EXPERIENCE = "experience"
    EDUCATION = "education"


class AlignedBy(StrEnum):
    KEY = "key"
    FALLBACK = "fallback"
    UNMATCHED = "unmatched"


@dataclass(frozen=True, slots=True)
class Alignment:
    """One entry's fate: the pair it formed, or the side it was left on.

    ``expected`` and ``actual`` are indices into the section's lists; exactly
    one is ``None`` when ``aligned_by`` is ``UNMATCHED``.
    """

    section: Section
    expected: int | None
    actual: int | None
    aligned_by: AlignedBy


def entry_key(entry: Entry) -> Key:
    if isinstance(entry, ExperienceEntry):
        start = (
            (None, None)
            if entry.start is None
            else (entry.start.year, entry.start.month)
        )
        return (canonicalise(entry.employer), start)
    return (canonicalise(entry.institution), canonicalise(entry.qualification))


def entry_leaves(entry: Entry) -> set[str]:
    """The canonicalised leaves an entry is made of, for overlap scoring."""
    dates = [d.expected for d in (entry.start, entry.end) if d is not None]
    if isinstance(entry, ExperienceEntry):
        scalars = [entry.title, entry.employer, entry.location, *dates]
        items = entry.bullets
    else:
        scalars = [entry.institution, entry.qualification, *dates]
        items = entry.details
    return {canonicalise(leaf) for leaf in [*scalars, *items] if leaf is not None}


def section_entries(content: CVContent, section: Section) -> list[Entry]:
    return list(
        content.experience if section is Section.EXPERIENCE else content.education
    )


def _key_pass(
    section: Section, actual: list[Entry], expected: list[Entry]
) -> list[Alignment]:
    # Equal keys pair up in list order, so two entries sharing a key (the same
    # employer, both undated) still pair one-to-one.
    unclaimed = list(range(len(actual)))
    pairs: list[Alignment] = []
    for e_index, e_entry in enumerate(expected):
        key = entry_key(e_entry)
        for a_index in unclaimed:
            if entry_key(actual[a_index]) == key:
                unclaimed.remove(a_index)
                pairs.append(Alignment(section, e_index, a_index, AlignedBy.KEY))
                break
    return pairs


def _jaccard(a: set[str], b: set[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _fallback_pass(
    section: Section,
    actual: list[Entry],
    expected: list[Entry],
    pairs: list[Alignment],
) -> list[Alignment]:
    # Greedy: the best-scoring remaining pair is taken, then the next, until
    # nothing left scores at the cutoff. Ties go to the earlier expected
    # entry, then the earlier actual one, so the result is deterministic.
    e_left = [i for i in range(len(expected)) if i not in {p.expected for p in pairs}]
    a_left = [i for i in range(len(actual)) if i not in {p.actual for p in pairs}]
    e_leaves = {i: entry_leaves(expected[i]) for i in e_left}
    a_leaves = {i: entry_leaves(actual[i]) for i in a_left}
    found: list[Alignment] = []
    while e_left and a_left:
        score, e_index, a_index = max(
            (
                (_jaccard(a_leaves[a], e_leaves[e]), e, a)
                for e in e_left
                for a in a_left
            ),
            key=lambda scored: (scored[0], -scored[1], -scored[2]),
        )
        if score < FALLBACK_CUTOFF:
            break
        e_left.remove(e_index)
        a_left.remove(a_index)
        found.append(Alignment(section, e_index, a_index, AlignedBy.FALLBACK))
    return found


def _unmatched(
    section: Section, actual: list[Entry], expected: list[Entry], pairs: list[Alignment]
) -> list[Alignment]:
    matched_expected = {pair.expected for pair in pairs}
    matched_actual = {pair.actual for pair in pairs}
    lost = [
        Alignment(section, index, None, AlignedBy.UNMATCHED)
        for index in range(len(expected))
        if index not in matched_expected
    ]
    invented = [
        Alignment(section, None, index, AlignedBy.UNMATCHED)
        for index in range(len(actual))
        if index not in matched_actual
    ]
    return [*lost, *invented]


def align(actual: CVContent, expected: CVContent) -> dict[Section, list[Alignment]]:
    """Every entry of both contents, per section, with how it aligned.

    Order within a section: by expected index, then unmatched actual entries
    by actual index, so a report is stable for a given pair of contents.
    """
    result: dict[Section, list[Alignment]] = {}
    for section in Section:
        a_entries = section_entries(actual, section)
        e_entries = section_entries(expected, section)
        pairs = _key_pass(section, a_entries, e_entries)
        pairs += _fallback_pass(section, a_entries, e_entries, pairs)
        everything = [*pairs, *_unmatched(section, a_entries, e_entries, pairs)]
        result[section] = sorted(everything, key=_report_order)
    return result


_LAST = float("inf")


def _report_order(alignment: Alignment) -> tuple[float, float]:
    expected = _LAST if alignment.expected is None else alignment.expected
    actual = _LAST if alignment.actual is None else alignment.actual
    return (expected, actual)
