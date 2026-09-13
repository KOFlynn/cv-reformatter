"""The primary invariant check: every rendered unit is a slice of the source.

Whole units against whole blocks (ADR-0007). The multiset metrics are
order-blind, so a bullet with two words swapped passes both; this check does
not, because the swapped bullet is a substring of no block. Template text is
whitelisted here by unit, not by word, which is what stops a template heading
being used as filler inside a bullet.
"""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding
from cvr.text import canonicalise

__all__ = ["provenance_violations"]


def provenance_violations(
    output_units: Iterable[str],
    source_blocks: Iterable[str],
    template_units: Iterable[str],
    date_map: Iterable[tuple[str, str]],
) -> list[Finding]:
    """Rendered units that are not a canonicalised substring of any source
    block, nor equal to a template unit, nor the rendered side of a
    ``date_map`` pair.

    Both sides are canonicalised, so a straightened quote passes here; that
    blind spot belongs to ``punctuation_fidelity``. A unit that canonicalises
    to nothing renders nothing and is skipped. Findings carry the unit as
    rendered, counted on the output side, sorted.
    """
    blocks = [canonicalise(block) for block in source_blocks]
    whole = {canonicalise(unit) for unit in template_units}
    whole |= {canonicalise(rendered) for _, rendered in date_map}
    violations: Counter[str] = Counter()
    for unit in output_units:
        text = canonicalise(unit)
        if not text or text in whole or any(text in block for block in blocks):
            continue
        violations[unit] += 1
    return sorted(
        Finding(what=unit, count=count, where="output")
        for unit, count in violations.items()
    )
