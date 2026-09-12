"""The single-column Layout: the clean control column of the style matrix.

``January 2020`` dates, Word list numbering for bullets, the contact block at
the top of the body, Candidate order throughout, no confusables, no photo.
Education sits after profile and skills. Anything the pipeline gets wrong
here it gets wrong on a tidy document, which is what a control is for.
"""

from typing import ClassVar

from docx import Document
from docx.document import Document as DocumentType

from cvr.golden.candidate import Candidate
from cvr.golden.layouts.base import (
    Decisions,
    FragmentPlacement,
    Layout,
    Plan,
    PlannedEntry,
)
from cvr.models import EducationEntry, ExperienceEntry

__all__ = ["SingleColumnLayout"]

_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


class SingleColumnLayout(Layout):
    name: ClassVar[str] = "single-column"
    contact_block: ClassVar[str] = "body-top"

    def format_date(self, month: int | None, year: int) -> str:
        return str(year) if month is None else f"{_MONTHS[month - 1]} {year}"

    def render(
        self, candidate: Candidate, plan: Plan, decisions: Decisions
    ) -> DocumentType:
        content, pii = candidate.content, candidate.pii
        document = Document()
        document.add_paragraph(content.name, style="Title")

        # Contact block at the top of the body, one line per detail.
        for line in [pii.phone, pii.email, *pii.address, *pii.urls, pii.dob]:
            if line:
                document.add_paragraph(line)
        for line in [pii.personal.nationality, pii.personal.marital_status]:
            if line:
                document.add_paragraph(line)

        if content.profile:
            _heading(document, "Profile")
            for paragraph in content.profile:
                document.add_paragraph(paragraph)

        if content.skills:
            _heading(document, "Key Skills")
            _bullets(document, content.skills)

        if plan.education:
            _heading(document, "Education")
            for planned in plan.education:
                _education(document, planned)

        if plan.experience:
            _heading(document, "Experience")
            for planned in plan.experience:
                _experience(document, planned)

        if content.certifications:
            _heading(document, "Certifications")
            _bullets(document, content.certifications)

        if content.additional:
            _heading(document, "Additional Information")
            for line in content.additional:
                document.add_paragraph(line)

        if pii.referees:
            _heading(document, "References")
            for referee in pii.referees:
                document.add_paragraph(referee.name).runs[0].bold = True
                for line in [referee.role, *referee.contact]:
                    if line:
                        document.add_paragraph(line)

        # Unplaceable fragments trail the body as plain paragraphs.
        for index, fragment in enumerate(candidate.unplaceable):
            document.add_paragraph(fragment)
            decisions.fragments.append(
                FragmentPlacement(index=index, location="body-end")
            )

        return document


def _heading(document: DocumentType, text: str) -> None:
    document.add_heading(text, level=1)


def _bullets(document: DocumentType, items: list[str]) -> None:
    # Word list numbering: the glyph comes from the style, not the text.
    for item in items:
        document.add_paragraph(item, style="List Bullet")


def _date_line(document: DocumentType, planned: PlannedEntry) -> None:
    parts = [part for part in (planned.start, planned.end) if part is not None]
    if parts:
        document.add_paragraph(" - ".join(parts))


def _experience(document: DocumentType, planned: PlannedEntry) -> None:
    entry = planned.entry
    assert isinstance(entry, ExperienceEntry)
    document.add_paragraph(entry.title).runs[0].bold = True
    where = (
        entry.employer
        if entry.location is None
        else f"{entry.employer}, {entry.location}"
    )
    document.add_paragraph(where).runs[0].italic = True
    _date_line(document, planned)
    _bullets(document, entry.bullets)


def _education(document: DocumentType, planned: PlannedEntry) -> None:
    entry = planned.entry
    assert isinstance(entry, EducationEntry)
    document.add_paragraph(entry.qualification).runs[0].bold = True
    document.add_paragraph(entry.institution).runs[0].italic = True
    _date_line(document, planned)
    _bullets(document, entry.details)
