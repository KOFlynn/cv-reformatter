"""The one thing every metric reports: what was wrong, how many times, and where."""

from dataclasses import dataclass

__all__ = ["Finding"]


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
