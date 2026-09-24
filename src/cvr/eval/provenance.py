"""The primary invariant check: every rendered unit is a slice of the source.

Whole units against whole blocks (ADR-0007). The multiset metrics are
order-blind, so a bullet with two words swapped passes both; this check does
not, because the swapped bullet is a substring of no block. Template text is
whitelisted here by unit, not by word, which is what stops a template heading
being used as filler inside a bullet.
"""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding, findings
from cvr.text import canonicalise

__all__ = ["provenance_violations"]


def provenance_violations(
    output_units: Iterable[str],
    source_blocks: Iterable[str],
    template_units: Iterable[str],
    date_map: Iterable[tuple[str, str]],
    split_map: Iterable[tuple[str, list[str]]] = (),
) -> list[Finding]:
    """Rendered units that are not a canonicalised substring of any source
    block, nor equal to a template unit, nor the rendered side of a
    ``date_map`` pair.

    A unit that ``split_map`` names is a multi-span unit and is checked only
    through its ordered raw slices, never the whole-unit substring rule:
    each slice must be a canonicalised substring of one common source block,
    the next always found after the last, so a join out of source order or
    across two blocks is caught even when the assembled whole happens to
    read as something else (ADR-0007 amendment). Both sides are
    canonicalised, so a straightened quote passes here; that blind spot
    belongs to ``punctuation_fidelity``. A unit that canonicalises to
    nothing renders nothing and is skipped. Findings carry the unit as
    rendered, counted on the output side, sorted.
    """
    blocks = [canonicalise(block) for block in source_blocks]
    # Template text and mapped dates are permitted as whole units only; a
    # template word inside a bullet is not template text.
    permitted = {canonicalise(unit) for unit in template_units}
    permitted |= {canonicalise(rendered) for _, rendered in date_map}
    joins = dict(split_map)
    violations: Counter[tuple[str, str]] = Counter()
    for unit in output_units:
        text = canonicalise(unit)
        if not text:
            continue
        if unit in joins:
            if not _slices_in_order(joins[unit], blocks):
                violations["output", unit] += 1
            continue
        if text in permitted or any(text in block for block in blocks):
            continue
        violations["output", unit] += 1
    return findings(violations)


def _slices_in_order(slices: Iterable[str], blocks: list[str]) -> bool:
    """Whether some one block holds every slice, each found strictly after
    the last, in the order given: the ascending, non-overlapping, one-block
    rule a multi-span unit must hold."""
    pieces = [canonicalise(piece) for piece in slices]
    if not pieces or any(not piece for piece in pieces):
        return False
    for block in blocks:
        position = 0
        for piece in pieces:
            found = block.find(piece, position)
            if found == -1:
                break
            position = found + len(piece)
        else:
            return True
    return False
