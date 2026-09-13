"""The Candidate: one fictional person's ground-truth CV content, PII and tags."""

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from cvr.models import PII, CVContent, Personal, Referee, StrictModel
from cvr.text import canonicalise

# PII, Personal and Referee are defined in cvr.models (eval needs them too) and
# re-exported here so the golden set remains the one place to import them from.
__all__ = ["PII", "Candidate", "Personal", "Referee", "Tag"]


class Tag(StrEnum):
    """A content trap a Candidate carries. Closed vocabulary; layout decisions are never tags.

    Each member has a one-line ``description`` and either a predicate over the
    Candidate (``holds``) or, where content alone cannot prove the trap, is
    author-declared: ``declared`` is true and ``holds`` is trivially true.
    """

    PUNCTUATION_IN_NAME = "punctuation-in-name"

    @property
    def description(self) -> str:
        return _SPECS[self].description

    @property
    def declared(self) -> bool:
        """True when the Candidate's author asserts the trap and no predicate can."""
        return _SPECS[self].predicate is None

    def holds(self, candidate: "Candidate") -> bool:
        predicate = _SPECS[self].predicate
        return True if predicate is None else predicate(candidate)


class Candidate(StrictModel):
    """Ground truth for one fictional person: identical across every Layout."""

    id: str = Field(min_length=1)
    content: CVContent
    pii: PII
    unplaceable: list[str] = Field(
        default_factory=list,
        description="Fragments that belong in no field, in source order: the expected review appendix.",
    )
    tags: list[Tag] = Field(default_factory=list)


def _punctuation_in_name(candidate: Candidate) -> bool:
    name = canonicalise(candidate.content.name)
    # A fada (or any diacritic) decomposes under NFD; a plain letter does not.
    return "'" in name or "-" in name or unicodedata.normalize("NFD", name) != name


@dataclass(frozen=True)
class _TagSpec:
    description: str
    predicate: Callable[[Candidate], bool] | None  # None: author-declared


_SPECS: dict[Tag, _TagSpec] = {
    Tag.PUNCTUATION_IN_NAME: _TagSpec(
        "Name carries an apostrophe, hyphen or a letter with a diacritic (a fada), "
        "so confusables and punctuation fidelity are exercised together.",
        _punctuation_in_name,
    ),
}
