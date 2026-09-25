"""The removal precision gate: text removed that the ground truth does not
allow its rule to remove.

``dropped_tokens`` counts every logged removal as accounted for, so a
labeller that deletes a content line under a PII rule loses candidate text
that no other hard gate sees; only placement recall moves, and that is
tunable. The design's promise is that the output loses nothing of the
candidate's except PII, so a wrongful removal is judged as a dropped token
is: any one is a finding.

Each text removal is checked against what may be removed under its own
rule: the Candidate's ``PII`` values for that rule (the ``PII`` docstring
maps each key to exactly one), and for ``RM_HEADING`` the headings the
Layout wrote. ``RM_PHOTO`` removes images, not text, and is out of scope.
Removals made by verify's backstops are judged the same as the labeller's.

Matching is on canonical text, as ``pii_leak`` matches: a removal passes if
its canonical text is a substring of one allowed value's, so a sub-slice
(one address line, a referee's phone out of their contact line) passes.
It is case-sensitive, since a removal is a slice of the source and the
source prints each value as written. What the metric cannot see is where a
removal came from: a job location ``Cork`` removed under ``RM_ADDRESS``
passes when ``Cork`` is also an address line, because the text is allowed.
"""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding, findings
from cvr.models import PII, Removal, RemovalRule, Span
from cvr.text import canonicalise

__all__ = ["removal_precision"]


def _allowed(pii: PII, headings: Iterable[str]) -> dict[RemovalRule, list[str]]:
    """What each rule may remove, canonicalised; absent values dropped."""
    values: dict[RemovalRule, list[str | None]] = {
        RemovalRule.PHONE: [pii.phone],
        RemovalRule.EMAIL: [pii.email],
        RemovalRule.ADDRESS: list(pii.address),
        RemovalRule.URL: list(pii.urls),
        RemovalRule.DOB: [pii.dob],
        RemovalRule.PERSONAL: [pii.personal.nationality, pii.personal.marital_status],
        RemovalRule.REFEREE: [
            detail
            for referee in pii.referees
            for detail in (referee.name, referee.role, *referee.contact)
        ],
        RemovalRule.HEADING: list(headings),
    }
    return {
        rule: [canonicalise(value) for value in texts if value]
        for rule, texts in values.items()
    }


def removal_precision(
    removals: Iterable[Removal], pii: PII, headings: Iterable[str]
) -> list[Finding]:
    """Every text removal not covered by an allowed value for its rule.

    ``removals`` is the Run's removal log; ``pii`` and ``headings`` (the
    section headings the Layout wrote) are the ground truth. A finding's
    ``where`` is the block the text was removed from and its ``what`` the
    rule and the canonical text; the same removal twice in one block is
    one finding of two. A removal whose canonical text is empty removed
    nothing but whitespace and passes.
    """
    allowed = _allowed(pii, headings)
    wrongful: Counter[tuple[str, str]] = Counter()
    for removal in removals:
        if not isinstance(removal.subject, Span):
            continue  # an image, RM_PHOTO's: not text
        text = canonicalise(removal.subject.text)
        if not text or any(text in value for value in allowed.get(removal.rule, [])):
            continue
        wrongful[(removal.subject.block_id, f"{removal.rule}: {text}")] += 1
    return findings(wrongful)
