"""Shared builders for render tests: a Candidate's ``CVContent`` down to the
``TransformedContent`` shape ``render`` takes.

``transform`` has its own tests for date splitting and multi-span joins;
here we only need what a Candidate's own content already states, since every
``DateValue.expected`` is transform's hand-written answer for that date.
"""

from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry, Span
from cvr.transform import (
    TransformedContent,
    TransformedEducation,
    TransformedExperience,
)

__all__ = ["to_transformed_content", "unplaced_spans"]


def unplaced_spans(*fragments: str) -> list[Span]:
    """Unplaced fragments as the Spans ``render`` takes. The block id and
    offsets are unexamined by anything under test here; only ``text`` is."""
    return [
        Span(block_id="body:0", start=0, end=len(text), text=text) for text in fragments
    ]


def _expected(date: DateValue | None) -> str | None:
    return None if date is None else date.expected


def _experience(entry: ExperienceEntry) -> TransformedExperience:
    return TransformedExperience(
        title=entry.title,
        employer=entry.employer,
        location=entry.location,
        start=_expected(entry.start),
        end=_expected(entry.end),
        bullets=list(entry.bullets),
    )


def _education(entry: EducationEntry) -> TransformedEducation:
    return TransformedEducation(
        institution=entry.institution,
        qualification=entry.qualification,
        start=_expected(entry.start),
        end=_expected(entry.end),
        details=list(entry.details),
    )


def to_transformed_content(content: CVContent) -> TransformedContent:
    """A Candidate's ``CVContent`` as the ``TransformedContent`` ``render``
    takes: what ``transform_content`` would have produced from it, using
    each date's hand-written ``expected`` directly."""
    return TransformedContent(
        name=content.name,
        profile=list(content.profile),
        skills=list(content.skills),
        education=[_education(entry) for entry in content.education],
        experience=[_experience(entry) for entry in content.experience],
        certifications=list(content.certifications),
        additional=list(content.additional),
    )
