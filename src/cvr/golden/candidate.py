"""The Candidate: one fictional person's ground-truth CV content, PII and tags."""

import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from cvr.models import (
    PII,
    CVContent,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    Personal,
    Referee,
    StrictModel,
)
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

    NO_PROFILE = "no-profile"
    TYPO = "typo"
    YEAR_ONLY_DATE = "year-only-date"
    LITERAL_DATE = "literal-date"
    UNDATED_ENTRY = "undated-entry"
    CURRENT_ROLE = "current-role"
    PII_IN_BULLET = "pii-in-bullet"
    UNPLACEABLE = "unplaceable"
    HAS_REFEREES = "has-referees"
    HAS_PERSONAL_DETAILS = "has-personal-details"
    DATE_IN_BODY_TEXT = "date-in-body-text"
    UNUSUAL_SECTIONS = "unusual-sections"
    NON_IE_LOCALE = "non-ie-locale"
    REPEAT_EMPLOYER = "repeat-employer"
    CONCURRENT_ROLES = "concurrent-roles"
    DUPLICATE_SKILL = "duplicate-skill"
    EMPTY_SECTIONS = "empty-sections"
    PUNCTUATION_IN_NAME = "punctuation-in-name"
    INLINE_SKILLS = "inline-skills"

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


# --- Predicates. Each takes the whole Candidate and answers one question.


def _entries(content: CVContent) -> list[ExperienceEntry | EducationEntry]:
    return [*content.experience, *content.education]


def _dates(content: CVContent) -> Iterator[DateValue]:
    for entry in _entries(content):
        yield from (date for date in (entry.start, entry.end) if date is not None)


def _body_strings(content: CVContent) -> Iterator[str]:
    """Every free-text leaf: where a date is content, never an entry date."""
    yield from content.profile
    for experience in content.experience:
        yield from experience.bullets
    for education in content.education:
        yield from education.details
    yield from content.certifications
    yield from content.additional


# A four-digit year standing alone as digits; "2000 euro" also matches, which
# is the point: any year-shaped text in a body string must be left alone.
_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def _no_profile(candidate: Candidate) -> bool:
    return candidate.content.profile == []


def _year_only_date(candidate: Candidate) -> bool:
    return any(
        date.year is not None
        and date.month is None
        and not date.present
        and date.literal is None
        for date in _dates(candidate.content)
    )


def _literal_date(candidate: Candidate) -> bool:
    return any(date.literal is not None for date in _dates(candidate.content))


def _undated_entry(candidate: Candidate) -> bool:
    return any(
        entry.start is None and entry.end is None
        for entry in _entries(candidate.content)
    )


def _present_roles(candidate: Candidate) -> int:
    return sum(
        1
        for entry in candidate.content.experience
        if entry.end is not None and entry.end.present
    )


def _current_role(candidate: Candidate) -> bool:
    return _present_roles(candidate) >= 1


def _concurrent_roles(candidate: Candidate) -> bool:
    return _present_roles(candidate) >= 2


def _unplaceable(candidate: Candidate) -> bool:
    return candidate.unplaceable != []


def _has_referees(candidate: Candidate) -> bool:
    return candidate.pii.referees != []


def _has_personal_details(candidate: Candidate) -> bool:
    pii = candidate.pii
    return bool(pii.dob or pii.personal.nationality or pii.personal.marital_status)


def _date_in_body_text(candidate: Candidate) -> bool:
    return any(_YEAR.search(text) for text in _body_strings(candidate.content))


def _has_duplicates(values: list[str]) -> bool:
    canonical = [canonicalise(value) for value in values]
    return len(set(canonical)) < len(canonical)


def _repeat_employer(candidate: Candidate) -> bool:
    return _has_duplicates([entry.employer for entry in candidate.content.experience])


def _duplicate_skill(candidate: Candidate) -> bool:
    return _has_duplicates(candidate.content.skills)


def _empty_sections(candidate: Candidate) -> bool:
    content = candidate.content
    return content.certifications == [] and content.additional == []


def _punctuation_in_name(candidate: Candidate) -> bool:
    name = canonicalise(candidate.content.name)
    # A fada (or any diacritic) decomposes under NFD; a plain letter does not.
    return "'" in name or "-" in name or unicodedata.normalize("NFD", name) != name


@dataclass(frozen=True)
class _TagSpec:
    description: str
    predicate: Callable[[Candidate], bool] | None  # None: author-declared


_SPECS: dict[Tag, _TagSpec] = {
    Tag.NO_PROFILE: _TagSpec(
        "No profile at all, so the template must render no profile heading.",
        _no_profile,
    ),
    Tag.TYPO: _TagSpec(
        "Declared: a content string carries a misspelling that must survive verbatim.",
        None,
    ),
    Tag.YEAR_ONLY_DATE: _TagSpec(
        "An entry date has a year and no month, so the output is YYYY with no month invented.",
        _year_only_date,
    ),
    Tag.LITERAL_DATE: _TagSpec(
        "An entry date is unparseable text ('Summer 2020') that must pass through verbatim.",
        _literal_date,
    ),
    Tag.UNDATED_ENTRY: _TagSpec(
        "An entry has neither start nor end, so it sorts last and prints no date line.",
        _undated_entry,
    ),
    Tag.CURRENT_ROLE: _TagSpec(
        "An experience entry ends Present, which sorts first and prints as the word.",
        _current_role,
    ),
    Tag.PII_IN_BULLET: _TagSpec(
        "Declared: the base Layout prints the phone at the end of the first experience "
        "bullet that ends without a full stop, so the fixture holds the expected text and "
        "every generated document exercises removal inside body text.",
        None,
    ),
    Tag.UNPLACEABLE: _TagSpec(
        "Carries fragments that belong in no field: the review appendix must hold exactly them.",
        _unplaceable,
    ),
    Tag.HAS_REFEREES: _TagSpec(
        "Lists referees with contact details, all removed under RM_REFEREE as one rule.",
        _has_referees,
    ),
    Tag.HAS_PERSONAL_DETAILS: _TagSpec(
        "Has a date of birth, nationality or marital status for RM_DOB and RM_PERSONAL.",
        _has_personal_details,
    ),
    Tag.DATE_IN_BODY_TEXT: _TagSpec(
        "A year sits inside a body string (certification, bullet, detail, additional line) "
        "and is content the date normaliser must not touch.",
        _date_in_body_text,
    ),
    Tag.UNUSUAL_SECTIONS: _TagSpec(
        "Declared: the source has sections the template lacks (Volunteering, Publications), "
        "whose lines are expected verbatim under additional information.",
        None,
    ),
    Tag.NON_IE_LOCALE: _TagSpec(
        "Declared: contact details, spellings and institutions are from outside Ireland "
        "(UK, DE or IN), so PII variants and date habits are not the Irish defaults.",
        None,
    ),
    Tag.REPEAT_EMPLOYER: _TagSpec(
        "Two experience entries share an employer, so alignment needs the start date too.",
        _repeat_employer,
    ),
    Tag.CONCURRENT_ROLES: _TagSpec(
        "Two experience entries both end Present, exercising the ordering tiebreak on start.",
        _concurrent_roles,
    ),
    Tag.DUPLICATE_SKILL: _TagSpec(
        "The same skill appears twice, so list alignment must respect multiplicity.",
        _duplicate_skill,
    ),
    Tag.EMPTY_SECTIONS: _TagSpec(
        "Certifications and additional information are both empty, so the template must "
        "leave no empty heading behind.",
        _empty_sections,
    ),
    Tag.PUNCTUATION_IN_NAME: _TagSpec(
        "Name carries an apostrophe, hyphen or a letter with a diacritic (a fada), "
        "so confusables and punctuation fidelity are exercised together.",
        _punctuation_in_name,
    ),
    Tag.INLINE_SKILLS: _TagSpec(
        "Declared: the skills came from one comma-separated line, so a Layout printing "
        "them inline exercises the split with parenthetical qualifiers kept attached.",
        None,
    ),
}
