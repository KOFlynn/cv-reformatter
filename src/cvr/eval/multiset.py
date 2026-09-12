"""The coarse multiset backstops: text appearing from, or vanishing into, nowhere.

Order-blind by design (ADR-0007): a swapped pair of words passes both. Their
job is to catch what provenance cannot express as a per-unit check, such as a
word that appears in the output but in no source block. Inputs are already
tokenised with ``cvr.text.tokenise``; nothing here normalises on its own.
"""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding
from cvr.text import tokenise

__all__ = ["added_tokens"]


def _findings(excess: Counter[str], where: str) -> list[Finding]:
    return sorted(
        Finding(what=token, count=count, where=where)
        for token, count in excess.items()
        if count > 0
    )


def added_tokens(
    source: Iterable[str],
    output: Iterable[str],
    template: Iterable[str],
    date_map: Iterable[tuple[str, str]],
) -> list[Finding]:
    """Output tokens minus source, template and mapped dates, as a multiset.

    ``date_map`` is the transform log's ``(source date text, rendered date
    text)`` pairs; only the rendered side is permitted here, tokenised the same
    way as everything else. Multiplicity counts: one more ``Python`` than the
    source and template together supply is a finding of one.
    """
    permitted = Counter(source) + Counter(template)
    for _, rendered in date_map:
        permitted.update(tokenise(rendered))
    return _findings(Counter(output) - permitted, where="output")
