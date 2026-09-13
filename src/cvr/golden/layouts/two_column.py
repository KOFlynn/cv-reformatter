"""The two-column table Layout: the style matrix's second column.

One two-cell table holds the whole CV. The left cell carries the contact
block and education; the right cell carries the name, summary, skills and
work history. ``01/2020`` dates, literal ``•`` bullets, experience reversed
(oldest first). Reading order is a trap in itself: the pipeline has to
realise the columns are not one stream of text.
"""

from typing import ClassVar

from docx import Document
from docx.document import Document as DocumentType
from docx.shared import Cm
from docx.table import _Cell

from cvr.golden.candidate import Candidate
from cvr.golden.layouts.base import (
    Decisions,
    FragmentPlacement,
    Layout,
    Plan,
    PlannedEntry,
    Section,
)
from cvr.models import EducationEntry, ExperienceEntry

__all__ = ["TwoColumnLayout"]

_LEFT_WIDTH = Cm(5.5)
_RIGHT_WIDTH = Cm(11.5)


class TwoColumnLayout(Layout):
    name: ClassVar[str] = "two-column"
    contact_block: ClassVar[str] = "left-column"

    def format_date(self, month: int | None, year: int) -> str:
        return str(year) if month is None else f"{month:02d}/{year}"

    def scramble(self, section: Section, indices: list[int]) -> list[int]:
        # Experience oldest first; education stays in Candidate order.
        return indices[::-1] if section == "experience" else indices

    def render(
        self, candidate: Candidate, plan: Plan, decisions: Decisions
    ) -> DocumentType:
        content, pii = candidate.content, candidate.pii
        document = Document()
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        left, right = table.rows[0].cells
        left.width, right.width = _LEFT_WIDTH, _RIGHT_WIDTH
        # Left column: contact block, then education.
        _heading(left, "Contact")
        _lines(left, [pii.phone, pii.email, *pii.address, *pii.urls, pii.dob])
        _lines(left, [pii.personal.nationality, pii.personal.marital_status])

        if plan.education:
            _heading(left, "Academic Background")
            for planned in plan.education:
                _education(left, planned)

        if pii.referees:
            _heading(left, "Referees")
            for referee in pii.referees:
                _line(left, referee.name, bold=True)
                _lines(left, [referee.role, *referee.contact])

        # Right column: name, then the rest.
        right.add_paragraph(content.name, style="Title")

        if content.profile:
            _heading(right, "Summary")
            _lines(right, content.profile)

        if content.skills:
            _heading(right, "Skills")
            _bullets(right, content.skills)

        if plan.experience:
            _heading(right, "Work History")
            for planned in plan.experience:
                _experience(right, planned)

        if content.certifications:
            _heading(right, "Certifications")
            _bullets(right, content.certifications)

        if content.additional:
            _heading(right, "Other Information")
            _lines(right, content.additional)

        # Unplaceable fragments trail the left column, under the referees.
        for index, fragment in enumerate(candidate.unplaceable):
            _line(left, fragment)
            decisions.fragments.append(
                FragmentPlacement(index=index, location="left-column-end")
            )

        return document


def _heading(cell: _Cell, text: str) -> None:
    cell.add_paragraph(text, style="Heading 1")


def _line(cell: _Cell, text: str, *, bold: bool = False, italic: bool = False) -> None:
    # Only set what is asked for: ``run.bold = False`` would write an explicit
    # off-toggle into the XML rather than nothing.
    run = cell.add_paragraph().add_run(text)
    if bold:
        run.bold = True
    if italic:
        run.italic = True


def _lines(cell: _Cell, texts: list[str | None]) -> None:
    """One paragraph per text, skipping absent values."""
    for text in texts:
        if text:
            _line(cell, text)


def _bullets(cell: _Cell, items: list[str]) -> None:
    # A literal bullet glyph in the text itself, not Word list numbering.
    for item in items:
        _line(cell, f"• {item}")


def _date_line(cell: _Cell, planned: PlannedEntry) -> None:
    parts = [part for part in (planned.start, planned.end) if part is not None]
    if parts:
        _line(cell, " - ".join(parts))


def _experience(cell: _Cell, planned: PlannedEntry[ExperienceEntry]) -> None:
    entry = planned.entry
    _line(cell, entry.title, bold=True)
    employer_line = (
        entry.employer
        if entry.location is None
        else f"{entry.employer}, {entry.location}"
    )
    _line(cell, employer_line, italic=True)
    _date_line(cell, planned)
    _bullets(cell, entry.bullets)


def _education(cell: _Cell, planned: PlannedEntry[EducationEntry]) -> None:
    entry = planned.entry
    _line(cell, entry.qualification, bold=True)
    _line(cell, entry.institution, italic=True)
    _date_line(cell, planned)
    _bullets(cell, entry.details)
