"""``render``: the pipeline's fifth node.

Fills the committed template through ``cvr.template.fill`` from what
``transform`` produced (``TransformedContent``, every leaf already a plain
string) plus the Run's unplaced Spans, in the order each already carries:
transform's entry order, and ``Run.unplaced``'s block-then-source order.
Composes nothing of its own; every composite line (employer and location
joined by a comma, a date range joined by an en dash) is composed by the
template's own Jinja, exactly as it was for the Phase 0 harness's
``CVContent`` (ADR-0006). ``fill`` still takes a ``CVContent``, so a rejected
leaf's ``None`` becomes an empty string here rather than reaching the
template as the literal word "None"; that is the one adaptation this module
makes, and it never invents wording.

Depends on ``cvr.models`` (``Span``), ``cvr.template`` (the committed
template and ``fill``) and, for the shape transform hands it,
``cvr.transform``. Never on ``verify``, ``parse``, ``label`` or ``eval``.
"""

from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry, Span
from cvr.template import fill
from cvr.transform import (
    TransformedContent,
    TransformedEducation,
    TransformedExperience,
)

__all__ = ["render"]


def _date(value: str | None) -> DateValue | None:
    return None if value is None else DateValue(expected=value)


def _experience(entry: TransformedExperience) -> ExperienceEntry:
    return ExperienceEntry(
        title=entry.title or "",
        employer=entry.employer or "",
        location=entry.location,
        start=_date(entry.start),
        end=_date(entry.end),
        bullets=list(entry.bullets),
    )


def _education(entry: TransformedEducation) -> EducationEntry:
    return EducationEntry(
        institution=entry.institution or "",
        qualification=entry.qualification or "",
        start=_date(entry.start),
        end=_date(entry.end),
        details=list(entry.details),
    )


def _to_cv_content(content: TransformedContent) -> CVContent:
    """``TransformedContent`` as the ``CVContent`` shape ``fill`` takes."""
    return CVContent(
        name=content.name or "",
        profile=list(content.profile),
        skills=list(content.skills),
        education=[_education(entry) for entry in content.education],
        experience=[_experience(entry) for entry in content.experience],
        certifications=list(content.certifications),
        additional=list(content.additional),
    )


def render(content: TransformedContent, unplaced: list[Span]) -> bytes:
    """The committed template filled with ``content`` and ``unplaced``, as
    ``.docx`` bytes. ``unplaced`` is printed in the order given; render does
    not reorder it (``Run.unplaced`` already carries source order)."""
    return fill(_to_cv_content(content), [span.text for span in unplaced])
