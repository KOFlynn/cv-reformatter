"""The text-box Layout: the style matrix's third column.

The contact block and the skills sit inside text boxes, which python-docx can
neither create nor read, so they are written as raw ``w:txbxContent`` XML and
python-docx's ``document.paragraphs`` never sees them. Anything the parser
gets wrong here it gets wrong on text it can only reach through the XML.
"""

from typing import ClassVar

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml import parse_xml
from lxml import etree

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

__all__ = ["TextBoxLayout"]

_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

# A VML text box: the form Word 2007 wrote and every later Word still opens.
# Unlike the DrawingML form with its VML fallback it carries the text once,
# so a document says each string exactly once.
_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)
_TEXT_BOX = (
    '<w:r {ns}><w:pict><v:shape id="{id}" type="#_x0000_t202" '
    'style="width:450pt;height:40pt;mso-position-horizontal:left" '
    'strokecolor="#7f7f7f"><v:textbox style="mso-fit-shape-to-text:t" '
    'inset="5pt,3pt,5pt,3pt">{content}</v:textbox></v:shape></w:pict></w:r>'
)


class TextBoxLayout(Layout):
    name: ClassVar[str] = "text-box"
    contact_block: ClassVar[str] = "text-box"

    def format_date(self, month: int | None, year: int) -> str:
        # A two-digit year is the trap; a bare ``'20`` for a year-only date is
        # not something a CV would say, so those print in full.
        if month is None:
            return str(year)
        return f"{_MONTHS[month - 1]} '{year % 100:02d}"

    def scramble(self, section: Section, indices: list[int]) -> list[int]:
        # Experience rotated by one (the first entry moved to the end) so the
        # most recent role is neither first nor last; education reversed.
        if section == "experience":
            return indices[1:] + indices[:1]
        return indices[::-1]

    def render(
        self, candidate: Candidate, plan: Plan, decisions: Decisions
    ) -> DocumentType:
        content, pii = candidate.content, candidate.pii
        document = Document()
        document.add_paragraph(content.name, style="Title")

        _text_box(
            document,
            shape_id="_x0000_s1025",
            texts=[
                pii.phone,
                pii.email,
                *pii.address,
                *pii.urls,
                pii.dob,
                pii.personal.nationality,
                pii.personal.marital_status,
            ],
        )

        if content.profile:
            document.add_heading("About Me", level=1)
            _lines(document, content.profile)

        if content.skills:
            document.add_heading("Core Competencies", level=1)
            _text_box(document, shape_id="_x0000_s1026", texts=content.skills)

        if plan.experience:
            document.add_heading("Professional Experience", level=1)
            for planned in plan.experience:
                _experience(document, planned)

        if plan.education:
            document.add_heading("Education & Training", level=1)
            for planned in plan.education:
                _education(document, planned)

        if content.certifications:
            document.add_heading("Certifications", level=1)
            _bullets(document, content.certifications)

        if content.additional:
            document.add_heading("Additional Information", level=1)
            _lines(document, content.additional)

        if pii.referees:
            document.add_heading("References", level=1)
            for referee in pii.referees:
                _line(document, referee.name, bold=True)
                _lines(document, [referee.role, *referee.contact])

        # Unplaceable fragments trail the body as plain paragraphs.
        for index, fragment in enumerate(candidate.unplaceable):
            _line(document, fragment)
            decisions.fragments.append(
                FragmentPlacement(index=index, location="body-end")
            )

        return document


def _line(
    document: DocumentType, text: str, *, bold: bool = False, italic: bool = False
) -> None:
    run = document.add_paragraph().add_run(text)
    if bold:
        run.bold = True
    if italic:
        run.italic = True


def _lines(document: DocumentType, texts: list[str | None]) -> None:
    for text in texts:
        if text:
            _line(document, text)


def _bullets(document: DocumentType, items: list[str]) -> None:
    # A literal hyphen typed into the text, the way a plain-text CV does it.
    for item in items:
        _line(document, f"- {item}")


def _date_line(document: DocumentType, planned: PlannedEntry) -> None:
    parts = [part for part in (planned.start, planned.end) if part is not None]
    if parts:
        _line(document, " - ".join(parts))


def _experience(document: DocumentType, planned: PlannedEntry[ExperienceEntry]) -> None:
    entry = planned.entry
    _line(document, entry.title, bold=True)
    employer_line = (
        entry.employer
        if entry.location is None
        else f"{entry.employer}, {entry.location}"
    )
    _line(document, employer_line, italic=True)
    _date_line(document, planned)
    _bullets(document, entry.bullets)


def _education(document: DocumentType, planned: PlannedEntry[EducationEntry]) -> None:
    entry = planned.entry
    _line(document, entry.qualification, bold=True)
    _line(document, entry.institution, italic=True)
    _date_line(document, planned)
    _bullets(document, entry.details)


def _text_box(
    document: DocumentType, *, shape_id: str, texts: list[str | None]
) -> None:
    """Append a paragraph holding a text box whose content is one paragraph per
    text, skipping absent values."""
    content = etree.Element(_w("txbxContent"))
    for text in texts:
        if text:
            paragraph = etree.SubElement(content, _w("p"))
            run = etree.SubElement(paragraph, _w("r"))
            t = etree.SubElement(run, _w("t"))
            t.text = text
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    xml = _TEXT_BOX.format(
        ns=_NS,
        id=shape_id,
        content=etree.tostring(content, encoding="unicode"),
    )
    document.add_paragraph()._p.append(parse_xml(xml))


def _w(tag: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{tag}"
