"""One claim ledger per block: the record of which raw slices are taken, by a
removal rule or by a field.

The ledger locates a quote on the block's canonical text and slices raw
through the offset map, so a curly quote in the source is matched by a
straight one in the reference and comes back curly. It knows nothing of the
fill order; ``verify`` owns that. It answers three questions: where does this
quote occur, what of a range is still free of removals (or of content), and
what is left unclaimed at the end.
"""

from dataclasses import dataclass
from enum import StrEnum

from cvr.models import SourceBlock, Span
from cvr.text import canonicalise, canonicalise_with_offsets

__all__ = ["Kind", "Ledger", "LedgerEntry", "Range"]

type Range = tuple[int, int]


class Kind(StrEnum):
    REMOVAL = "removal"
    CONTENT = "content"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """A claimed raw range: ``claimant`` is the removal rule id or the path of
    the field (``experience[1].bullets[2]``)."""

    start: int
    end: int
    claimant: str
    kind: Kind


class Ledger:
    """The claims over one block, in the order they were made."""

    def __init__(self, block: SourceBlock) -> None:
        self.block = block
        self.canonical = canonicalise_with_offsets(block.text)
        self.entries: list[LedgerEntry] = []

    def occurrences(self, quote: str) -> list[Range]:
        """The raw range of every occurrence of ``quote`` in the block,
        matched on canonical text, in source order."""
        needle = canonicalise(quote)
        if not needle:
            return []
        found: list[Range] = []
        text = self.canonical.text
        at = text.find(needle)
        while at != -1:
            found.append(self.raw_range(at, at + len(needle)))
            at = text.find(needle, at + 1)
        return found

    def raw_range(self, start: int, end: int) -> Range:
        """The raw range behind canonical ``[start, end)``."""
        return self.canonical.offsets[start], self.canonical.ends[end - 1]

    def overlaps(self, start: int, end: int, kind: Kind) -> bool:
        return any(
            entry.kind is kind and entry.start < end and start < entry.end
            for entry in self.entries
        )

    def free(self, start: int, end: int, kind: Kind | None = None) -> list[Range]:
        """What is left of ``[start, end)`` once the entries of ``kind`` (every
        entry when ``None``) are taken out: none, one or several ranges,
        ascending."""
        pieces: list[Range] = []
        at = start
        blocking = sorted(
            (entry for entry in self.entries if kind is None or entry.kind is kind),
            key=lambda entry: entry.start,
        )
        for entry in blocking:
            if entry.end <= at or entry.start >= end:
                continue
            if entry.start > at:
                pieces.append((at, entry.start))
            at = max(at, entry.end)
        if at < end:
            pieces.append((at, end))
        return pieces

    def clipped(self, start: int, end: int) -> list[Range]:
        """``[start, end)`` clipped around the removals, each piece without
        the whitespace at its edges and pieces of nothing else dropped.
        Clipping leaves the space that separated a removed phone from its
        bullet; that space is residue, not content."""
        text = self.block.text
        pieces: list[Range] = []
        for piece_start, piece_end in self.free(start, end, Kind.REMOVAL):
            while piece_start < piece_end and text[piece_start].isspace():
                piece_start += 1
            while piece_end > piece_start and text[piece_end - 1].isspace():
                piece_end -= 1
            if piece_start < piece_end:
                pieces.append((piece_start, piece_end))
        return pieces

    def whole(self) -> Range:
        return 0, len(self.block.text)

    def span(self, start: int, end: int) -> Span:
        """The Span for raw ``[start, end)`` of this block."""
        return Span(
            block_id=self.block.id,
            start=start,
            end=end,
            text=self.block.text[start:end],
        )

    def claim(self, start: int, end: int, claimant: str, kind: Kind) -> Span:
        self.entries.append(LedgerEntry(start, end, claimant, kind))
        return self.span(start, end)

    def has_content(self) -> bool:
        return any(entry.kind is Kind.CONTENT for entry in self.entries)

    def residue(self) -> list[Range]:
        """Every unclaimed raw range of the block, ascending."""
        return self.free(*self.whole())

    def sorted_entries(self) -> list[LedgerEntry]:
        return sorted(self.entries, key=lambda entry: (entry.start, entry.end))
