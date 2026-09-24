"""The adapter: the inverse of ``render``, walking a rendered document back
to leaves by field type (name, profile, skills, education entries,
experience entries, certifications, additional, appendix) so the Phase 0
eval metrics can be fed from real output without changing (ADR-0007
amendment).

Two composite lines are recomposed on the way out, each an approximation
documented rather than mitigated, in the spirit of the text-box
reading-order approximation of ADR-0008:

- The employer/location line is split on the first ``", "``, because the
  template inserts exactly one such separator and no employer name in the
  golden set contains a comma of its own. An employer that did would be
  misread as ending at its first comma.
- The date line is told apart from a plain "details" paragraph. Experience
  bullets carry their own "List Bullet" style, so there the distinction is
  free; education's "details" share the date line's plain style, so the
  date line is recognised by shape instead: it either joins two pieces with
  the template's own " – " or is itself one of the normaliser's three
  formatted shapes (``MM/YYYY``, ``YYYY``, ``Present``). A lone literal date
  with nothing else in the entry to confuse it for is read as the entry's
  end, matching the rule that produced it (``transform.dates``); a lone
  literal date sitting where it could be mistaken for a details line is the
  one shape this does not attempt to recognise on pattern alone, and none
  of the golden set's Candidates produce it.
"""

import re
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.text.paragraph import Paragraph

from cvr.template import BANNER
from cvr.transform import (
    TransformedContent,
    TransformedEducation,
    TransformedExperience,
)

__all__ = ["Adapted", "adapt"]

_HEADING_STYLE = "Heading 1"
_BULLET_STYLE = "List Bullet"

_SECTIONS = {
    "Profile": "profile",
    "Key Skills": "skills",
    "Education": "education",
    "Experience": "experience",
    "Certifications": "certifications",
    "Additional Information": "additional",
}

# The normaliser's three formatted shapes (transform.dates); a literal date
# is not matched here, only recognised by the " – " join it may sit in.
_DATE_TOKEN = re.compile(r"\A(?:\d{1,2}/\d{4}|\d{4}|Present)\Z")
_DATE_JOIN = " – "


@dataclass(frozen=True, slots=True)
class Adapted:
    """A rendered document's leaves: the content in ``TransformedContent``
    shape, plus the review appendix's fragments in document order."""

    content: TransformedContent
    appendix: list[str]


def _text(paragraph: Paragraph) -> str:
    return paragraph.text


def _style(paragraph: Paragraph) -> str:
    return paragraph.style.name if paragraph.style is not None else ""


def _is_bold(paragraph: Paragraph) -> bool:
    return bool(paragraph.runs) and bool(paragraph.runs[0].bold)


def _is_section_end(paragraph: Paragraph) -> bool:
    return _style(paragraph) == _HEADING_STYLE or _text(paragraph) == BANNER


def _none_if_blank(text: str) -> str | None:
    return text or None


def _is_date_line(text: str) -> bool:
    return _DATE_JOIN in text or bool(_DATE_TOKEN.match(text))


def _split_date_line(text: str) -> tuple[str | None, str | None]:
    if _DATE_JOIN in text:
        start, end = text.split(_DATE_JOIN, 1)
        return start, end
    # A lone date is always the entry's end (transform.dates' rule).
    return None, text


def _split_employer_location(text: str) -> tuple[str | None, str | None]:
    if ", " in text:
        employer, location = text.split(", ", 1)
        return _none_if_blank(employer), _none_if_blank(location)
    return _none_if_blank(text), None


def _read_plain_list(paragraphs: list[Paragraph], index: int) -> tuple[int, list[str]]:
    items: list[str] = []
    while index < len(paragraphs) and not _is_section_end(paragraphs[index]):
        items.append(_text(paragraphs[index]))
        index += 1
    return index, items


def _read_bullet_list(paragraphs: list[Paragraph], index: int) -> tuple[int, list[str]]:
    items: list[str] = []
    while index < len(paragraphs) and _style(paragraphs[index]) == _BULLET_STYLE:
        items.append(_text(paragraphs[index]))
        index += 1
    return index, items


def _read_date_line(
    paragraphs: list[Paragraph], index: int, *, needs_shape: bool
) -> tuple[int, str | None, str | None]:
    """The entry's date line at ``index``, if that is what sits there,
    else nothing consumed. ``needs_shape`` is set for education, whose
    "details" paragraphs share the date line's plain style; experience's
    bullets carry their own style, so there any plain, non-bold paragraph in
    the slot is unambiguously the date line."""
    if index >= len(paragraphs):
        return index, None, None
    candidate = paragraphs[index]
    if (
        _is_bold(candidate)
        or _style(candidate) == _BULLET_STYLE
        or _is_section_end(candidate)
    ):
        return index, None, None
    text = _text(candidate)
    if needs_shape and not _is_date_line(text):
        return index, None, None
    start, end = _split_date_line(text)
    return index + 1, start, end


def _read_experience(
    paragraphs: list[Paragraph], index: int
) -> tuple[int, list[TransformedExperience]]:
    entries: list[TransformedExperience] = []
    while index < len(paragraphs) and not _is_section_end(paragraphs[index]):
        title = _none_if_blank(_text(paragraphs[index]))
        index += 1
        employer, location = _split_employer_location(_text(paragraphs[index]))
        index += 1
        index, start, end = _read_date_line(paragraphs, index, needs_shape=False)
        index, bullets = _read_bullet_list(paragraphs, index)
        entries.append(
            TransformedExperience(
                title=title,
                employer=employer,
                location=location,
                start=start,
                end=end,
                bullets=bullets,
            )
        )
    return index, entries


def _read_education(
    paragraphs: list[Paragraph], index: int
) -> tuple[int, list[TransformedEducation]]:
    entries: list[TransformedEducation] = []
    while index < len(paragraphs) and not _is_section_end(paragraphs[index]):
        qualification = _none_if_blank(_text(paragraphs[index]))
        index += 1
        institution = _none_if_blank(_text(paragraphs[index]))
        index += 1
        index, start, end = _read_date_line(paragraphs, index, needs_shape=True)
        details: list[str] = []
        while (
            index < len(paragraphs)
            and not _is_section_end(paragraphs[index])
            and (not _is_bold(paragraphs[index]))
        ):
            details.append(_text(paragraphs[index]))
            index += 1
        entries.append(
            TransformedEducation(
                institution=institution,
                qualification=qualification,
                start=start,
                end=end,
                details=details,
            )
        )
    return index, entries


def adapt(document: bytes) -> Adapted:
    """A rendered ``.docx``'s leaves, as the inverse of ``render``."""
    docx = Document(BytesIO(document))
    paragraphs = docx.paragraphs
    name = _none_if_blank(_text(paragraphs[0])) if paragraphs else None
    index = 1

    profile: list[str] = []
    skills: list[str] = []
    education: list[TransformedEducation] = []
    experience: list[TransformedExperience] = []
    certifications: list[str] = []
    additional: list[str] = []
    appendix: list[str] = []

    while index < len(paragraphs):
        paragraph = paragraphs[index]
        if _text(paragraph) == BANNER:
            appendix = [_text(p) for p in paragraphs[index + 1 :]]
            break
        if _style(paragraph) != _HEADING_STYLE:
            index += 1
            continue
        section = _SECTIONS.get(_text(paragraph))
        index += 1
        if section == "profile":
            index, profile = _read_plain_list(paragraphs, index)
        elif section == "skills":
            index, skills = _read_bullet_list(paragraphs, index)
        elif section == "education":
            index, education = _read_education(paragraphs, index)
        elif section == "experience":
            index, experience = _read_experience(paragraphs, index)
        elif section == "certifications":
            index, certifications = _read_bullet_list(paragraphs, index)
        elif section == "additional":
            index, additional = _read_plain_list(paragraphs, index)

    return Adapted(
        content=TransformedContent(
            name=name,
            profile=profile,
            skills=skills,
            education=education,
            experience=experience,
            certifications=certifications,
            additional=additional,
        ),
        appendix=appendix,
    )
