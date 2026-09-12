"""The Candidate: one fictional person's ground-truth CV content, PII and tags."""

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cvr.models import CVContent
from cvr.text import canonicalise

__all__ = ["PII", "Candidate", "Personal", "Referee", "Tag"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Referee(_Strict):
    """Removed under RM_REFEREE: the name, role and every contact line."""

    name: str
    role: str | None = None
    contact: list[str] = []


class Personal(_Strict):
    """Removed under RM_PERSONAL."""

    nationality: str | None = None
    marital_status: str | None = None


class PII(_Strict):
    """Values that must be removed, grouped so each key maps to exactly one removal rule.

    ``phone`` RM_PHONE, ``email`` RM_EMAIL, ``address`` RM_ADDRESS (one line per
    item), ``urls`` RM_URL, ``dob`` RM_DOB, ``personal`` RM_PERSONAL, ``referees``
    RM_REFEREE. There is no ``photo`` key: the photo is a Layout decision and
    RM_PHOTO has no fixture value, as RM_HEADING has none.
    """

    phone: str | None = None
    email: str | None = None
    address: list[str] = []
    urls: list[str] = []
    dob: str | None = None
    personal: Personal = Personal()
    referees: list[Referee] = []


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
        """True when the fixture author asserts the trap and no predicate can."""
        return _SPECS[self].predicate is None

    def holds(self, candidate: "Candidate") -> bool:
        predicate = _SPECS[self].predicate
        return True if predicate is None else predicate(candidate)


class Candidate(_Strict):
    """Ground truth for one fictional person: identical across every Layout."""

    id: str = Field(min_length=1)
    content: CVContent
    pii: PII
    unplaceable: list[str] = Field(
        default=[],
        description="Fragments that belong in no field, in source order: the expected review appendix.",
    )
    tags: list[Tag] = []


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
        "Name carries an apostrophe, hyphen or fada, so confusables and punctuation "
        "fidelity are exercised together.",
        _punctuation_in_name,
    ),
}
