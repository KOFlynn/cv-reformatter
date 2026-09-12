"""Ordering: are the entries the pipeline did place in the expected order?

Computed over the matched subsequence only, using the same alignment as
placement accuracy, so an entry with a misspelt employer is judged on where
it sits rather than doubly punished for its key. Entries no pass could pair
are left out of the sequence and counted alongside, so a correct sequence
over two of three entries is reported as exactly that, never as green.
"""

from dataclasses import dataclass

from cvr.eval.alignment import (
    AlignedBy,
    Key,
    Section,
    align,
    entry_key,
    section_entries,
)
from cvr.models import CVContent

__all__ = ["OrderingReport", "SectionOrdering", "ordering_report"]


@dataclass(frozen=True, slots=True)
class SectionOrdering:
    """The matched entries' keys in expected order and in actual order.

    Each matched pair is labelled by the expected entry's key, so a pair found
    on the fallback pass appears under the key it should have had.
    """

    expected: tuple[Key, ...]
    actual: tuple[Key, ...]
    unmatched: int

    @property
    def correct(self) -> bool:
        return self.expected == self.actual


@dataclass(frozen=True, slots=True)
class OrderingReport:
    sections: dict[Section, SectionOrdering]

    @property
    def correct(self) -> bool:
        return all(section.correct for section in self.sections.values())

    @property
    def unmatched(self) -> dict[Section, int]:
        return {name: section.unmatched for name, section in self.sections.items()}


def ordering_report(actual: CVContent, expected: CVContent) -> OrderingReport:
    sections: dict[Section, SectionOrdering] = {}
    for section, alignments in align(actual, expected).items():
        e_entries = section_entries(expected, section)
        pairs = [a for a in alignments if a.aligned_by is not AlignedBy.UNMATCHED]
        # ``align`` lists pairs in expected order already; the actual order is
        # the same pairs sorted by where the actual side put them.
        in_expected_order = tuple(entry_key(e_entries[p.expected]) for p in pairs)
        in_actual_order = tuple(
            entry_key(e_entries[p.expected])
            for p in sorted(pairs, key=lambda p: p.actual)
        )
        sections[section] = SectionOrdering(
            in_expected_order, in_actual_order, len(alignments) - len(pairs)
        )
    return OrderingReport(sections)
