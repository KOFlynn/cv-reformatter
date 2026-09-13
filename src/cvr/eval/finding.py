"""The one thing every metric reports: what was wrong, how many times, and where."""

from collections.abc import Mapping
from dataclasses import dataclass

__all__ = ["Finding", "findings"]


@dataclass(frozen=True, order=True, kw_only=True, slots=True)
class Finding:
    """One item a metric reports. Metrics return findings sorted, so report
    diffs are stable: by ``where``, then ``what``, then ``count`` (the field
    order below; construction is keyword-only so call sites can read
    what/count/where regardless).

    For the multiset metrics ``where`` names the side of the comparison the
    token was counted on (``"output"`` for added, ``"source"`` for dropped),
    because token lists carry no position.
    """

    where: str
    what: str
    count: int


def findings(counts: Mapping[tuple[str, str], int]) -> list[Finding]:
    """Sorted findings from a count per ``(where, what)``; zero counts dropped.

    Every metric that counts occurrences ends the same way, so the shape
    lives here once: metrics own what they count, not how it is reported.
    """
    return sorted(
        Finding(where=where, what=what, count=count)
        for (where, what), count in counts.items()
        if count > 0
    )
