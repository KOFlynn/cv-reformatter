"""The guard on provenance's blind spot: raw span against raw unit.

Every other metric canonicalises both sides, so a renderer that silently
straightens a curly apostrophe passes all of them (ADR-0007). This one reads
the raw located source span and the raw rendered unit and asks whether they
are the same string, byte for byte. It does not share the confusable table
with ``canonicalise``, so a mapping missing from that table is not a blind
spot here.

A reported metric first; promoted to a hard gate after the Phase 1 baseline.
"""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding, findings

__all__ = ["punctuation_fidelity"]

_END = "(end)"


def _name(text: str, position: int) -> str:
    if position >= len(text):
        return _END
    char = text[position]
    # repr, so a space or an invisible character is readable in a report.
    return f"{char!r} (U+{ord(char):04X})"


def _first_difference(span: str, unit: str) -> str:
    position = 0
    while position < min(len(span), len(unit)) and span[position] == unit[position]:
        position += 1
    return f"{_name(span, position)} -> {_name(unit, position)}"


def punctuation_fidelity(pairs: Iterable[tuple[str, str]]) -> list[Finding]:
    """Pairs of ``(raw located span, raw rendered unit)`` whose two sides differ.

    No canonicalisation, no NFC: a decomposed accent is as much a change as a
    straightened quote. Each finding names the rendered unit (``where``) and
    the first differing character on each side as ``'<char>' (U+XXXX)``
    (``what``), with ``(end)`` when one side has run out; the same difference
    in the same unit twice is one finding of two. Sorted.
    """
    differences: Counter[tuple[str, str]] = Counter()
    for span, unit in pairs:
        if span != unit:
            differences[unit, _first_difference(span, unit)] += 1
    return findings(differences)
