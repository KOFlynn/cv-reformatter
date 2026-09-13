"""The header/footer Layout: the style matrix's fourth column.

The contact block is not in the body at all: phone and email sit in the page
header, address and URLs in the page footer, so a pipeline that reads only
body paragraphs never sees them and leaks them. ``2020-01`` dates, literal
``–`` bullets, education at the very bottom, experience and education both
reversed (oldest first), zero-width spaces and curly apostrophes from the
shared confusable table.
"""

from typing import ClassVar, Protocol

from docx import Document
from docx.document import Document as DocumentType
from docx.text.paragraph import Paragraph

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

__all__ = ["HeaderFooterLayout"]

_BULLET = "–"
_ZWSP = "\u200b"
_APOSTROPHE = "’"


class _Container(Protocol):
    """What the body, a header and a footer have in common: python-docx has
    no shared base for the three, so this names the two members used here."""

    @property
    def paragraphs(self) -> list[Paragraph]: ...

    def add_paragraph(self) -> Paragraph: ...


class HeaderFooterLayout(Layout):
    name: ClassVar[str] = "header-footer"
    contact_block: ClassVar[str] = "header-footer"

    def format_date(self, month: int | None, year: int) -> str:
        return str(year) if month is None else f"{year}-{month:02d}"

    def scramble(self, section: Section, indices: list[int]) -> list[int]:
        # Both sections oldest first.
        return indices[::-1]

    def render(
        self, candidate: Candidate, plan: Plan, decisions: Decisions
    ) -> DocumentType:
        content, pii = candidate.content, candidate.pii
        document = Document()
        section = document.sections[0]

        # Header: phone and email. Footer: address and URLs. A fresh header or
        # footer already holds one empty paragraph; the first line goes into it.
        _lines(section.header, [pii.phone, pii.email], decisions)
        _lines(section.footer, [*pii.address, *pii.urls], decisions)

        body = document
        body.add_paragraph(_curl(content.name, decisions), style="Title")
        _lines(
            body,
            [pii.dob, pii.personal.nationality, pii.personal.marital_status],
            decisions,
        )

        if content.profile:
            body.add_heading("Personal Statement", level=1)
            _lines(body, content.profile, decisions)

        if content.skills:
            body.add_heading("Technical Skills", level=1)
            _bullets(body, content.skills, decisions)

        if plan.experience:
            body.add_heading("Employment", level=1)
            for planned in plan.experience:
                _experience(body, planned, decisions)

        if content.certifications:
            body.add_heading("Certifications", level=1)
            _bullets(body, content.certifications, decisions)

        if content.additional:
            body.add_heading("Further Information", level=1)
            _lines(body, content.additional, decisions)

        if pii.referees:
            body.add_heading("Referees", level=1)
            for referee in pii.referees:
                _line(body, referee.name, decisions, bold=True)
                _lines(body, [referee.role, *referee.contact], decisions)

        # Education at the very bottom of the body, after everything else.
        if plan.education:
            body.add_heading("Qualifications", level=1)
            for planned in plan.education:
                _education(body, planned, decisions)

        # Unplaceable fragments trail the footer, under the contact lines: text
        # a pipeline reading only the body never sees, in a part it must still
        # sweep for the appendix.
        for index, fragment in enumerate(candidate.unplaceable):
            _line(section.footer, fragment, decisions)
            decisions.fragments.append(
                FragmentPlacement(index=index, location="footer-end")
            )

        return document


def _next_paragraph(container: _Container) -> Paragraph:
    """The next paragraph to write into: a header or footer's one empty
    paragraph while it is still empty, otherwise a fresh one."""
    paragraphs = container.paragraphs
    if len(paragraphs) == 1 and not paragraphs[0].text:
        return paragraphs[0]
    return container.add_paragraph()


def _curl(text: str, decisions: Decisions) -> str:
    """Word's smart apostrophe: every straight apostrophe becomes a right single
    quote from the shared confusable table, recorded as injected."""
    if "'" in text:
        decisions.injected(_APOSTROPHE)
        text = text.replace("'", _APOSTROPHE)
    return text


def _line(
    container: _Container,
    text: str,
    decisions: Decisions,
    *,
    bold: bool = False,
    italic: bool = False,
) -> None:
    """One paragraph of content or PII text, apostrophes curled."""
    # Only set what is asked for: ``run.bold = False`` would write an explicit
    # off-toggle into the XML rather than nothing.
    run = _next_paragraph(container).add_run(_curl(text, decisions))
    if bold:
        run.bold = True
    if italic:
        run.italic = True


def _lines(
    container: _Container, texts: list[str | None], decisions: Decisions
) -> None:
    """One paragraph per text, skipping absent values."""
    for text in texts:
        if text:
            _line(container, text, decisions)


def _bullets(container: _Container, items: list[str], decisions: Decisions) -> None:
    """A literal en dash as the bullet glyph, in the text itself, with a
    zero-width space from the shared table between it and the item: the kind
    of invisible character a web-to-Word paste leaves behind."""
    for item in items:
        decisions.injected(_ZWSP)
        _line(container, f"{_BULLET} {_ZWSP}{item}", decisions)


def _date_line(container: _Container, planned: PlannedEntry) -> None:
    """``2022-03 to 2026-07``: joined by a word, since a dash between
    dash-separated dates reads ambiguously and the column's confusables are
    the zero-width space and the curly apostrophe only. Written uninjected,
    so the document prints exactly the strings the manifest says it did,
    literal dates included."""
    parts = [part for part in (planned.start, planned.end) if part is not None]
    if parts:
        _next_paragraph(container).add_run(" to ".join(parts))


def _experience(
    container: _Container, planned: PlannedEntry[ExperienceEntry], decisions: Decisions
) -> None:
    entry = planned.entry
    _line(container, entry.title, decisions, bold=True)
    employer_line = (
        entry.employer
        if entry.location is None
        else f"{entry.employer}, {entry.location}"
    )
    _line(container, employer_line, decisions, italic=True)
    _date_line(container, planned)
    _bullets(container, entry.bullets, decisions)


def _education(
    container: _Container, planned: PlannedEntry[EducationEntry], decisions: Decisions
) -> None:
    entry = planned.entry
    _line(container, entry.qualification, decisions, bold=True)
    _line(container, entry.institution, decisions, italic=True)
    _date_line(container, planned)
    _bullets(container, entry.details, decisions)
