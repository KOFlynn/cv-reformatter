"""The text-box Layout: the style matrix's third column.

The contact block and the skills sit inside text boxes, which python-docx can
neither create nor read, so they are written as raw ``w:txbxContent`` XML and
python-docx's ``document.paragraphs`` never sees them. Anything the parser
gets wrong here it gets wrong on text it can only reach through the XML.

``Jan '20`` dates with a non-breaking space between month and year, non-
breaking spaces in the phone number, a soft hyphen in the first long word of
each profile paragraph and bullet, literal ``-`` bullets, education after
experience, experience rotated by one and education reversed.
"""

import re
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

_NBSP = "\u00a0"
_SOFT_HYPHEN = "\u00ad"
# A soft hyphen goes after the fifth letter of the first word of ten or more
# letters: invisible in Word, and a trap for anything that compares raw text.
_LONG_WORD = re.compile(r"[A-Za-z]{5}(?=[A-Za-z]{5,})")

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

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# A VML text box: the form Word 2007 wrote and every later Word still opens.
# Unlike the DrawingML form with its VML fallback it carries the text once,
# so a document says each string exactly once.
# Word declares the preset text-box shape once, before the first shape that
# refers to it; the writer does the same.
_SHAPE_TYPE = (
    '<v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202" '
    'path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/>'
    '<v:path gradientshapeok="t" o:connecttype="rect"/></v:shapetype>'
)
_TEXT_BOX = (
    f'<w:r xmlns:w="{_W}" xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office">'
    '<w:pict>{shape_type}<v:shape id="{id}" type="#_x0000_t202" '
    'style="width:450pt;height:40pt;mso-position-horizontal:left" '
    'strokecolor="#7f7f7f"><v:textbox style="mso-fit-shape-to-text:t" '
    'inset="5pt,3pt,5pt,3pt">{content}</v:textbox></v:shape></w:pict></w:r>'
)


class TextBoxLayout(Layout):
    name: ClassVar[str] = "text-box"
    contact_block: ClassVar[str] = "text-box"

    def format_date(self, month: int | None, year: int) -> str:
        # A two-digit year is the trap; a bare ``'20`` for a year-only date is
        # not something a CV would say, so those print in full. The space is
        # non-breaking, so the manifest's printed string is what the document
        # really carries.
        if month is None:
            return str(year)
        return f"{_MONTHS[month - 1]}{_NBSP}'{year % 100:02d}"

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
        writer = _Writer(Document(), decisions)
        writer.document.add_paragraph(content.name, style="Title")

        writer.text_box(
            shape_id="_x0000_s1025",
            texts=[
                writer.non_breaking(pii.phone),
                pii.email,
                *pii.address,
                *pii.urls,
                pii.dob,
                pii.personal.nationality,
                pii.personal.marital_status,
            ],
        )

        if content.profile:
            writer.heading("About Me")
            writer.lines([writer.soft_hyphenated(text) for text in content.profile])

        if content.skills:
            writer.heading("Core Competencies")
            writer.text_box(shape_id="_x0000_s1026", texts=content.skills)

        if plan.experience:
            writer.heading("Professional Experience")
            for planned in plan.experience:
                writer.experience(planned)

        if plan.education:
            writer.heading("Education & Training")
            for planned in plan.education:
                writer.education(planned)

        if content.certifications:
            writer.heading("Certifications")
            writer.bullets(content.certifications)

        if content.additional:
            writer.heading("Additional Information")
            writer.lines(content.additional)

        if pii.referees:
            writer.heading("References")
            for referee in pii.referees:
                writer.line(referee.name, bold=True)
                writer.lines([referee.role, *referee.contact])

        # Unplaceable fragments trail the body as plain paragraphs.
        for index, fragment in enumerate(candidate.unplaceable):
            writer.line(fragment)
            decisions.fragments.append(
                FragmentPlacement(index=index, location="body-end")
            )

        return writer.document


class _Writer:
    """Writes the document and records, on the Decisions, each confusable at
    the point it is injected."""

    def __init__(self, document: DocumentType, decisions: Decisions) -> None:
        self.document = document
        self.decisions = decisions
        self._shape_type_declared = False

    # --- Injections

    def non_breaking(self, text: str | None) -> str | None:
        """Every space made non-breaking, the way a phone number often is."""
        if not text or " " not in text:
            return text
        self.decisions.injected(_NBSP)
        return text.replace(" ", _NBSP)

    def soft_hyphenated(self, text: str) -> str:
        """A soft hyphen inside the first long word, if there is one."""
        hyphenated = _LONG_WORD.sub(lambda m: m.group() + _SOFT_HYPHEN, text, count=1)
        if hyphenated != text:
            self.decisions.injected(_SOFT_HYPHEN)
        return hyphenated

    # --- Body

    def heading(self, text: str) -> None:
        self.document.add_heading(text, level=1)

    def line(self, text: str, *, bold: bool = False, italic: bool = False) -> None:
        # Only set what is asked for: ``run.bold = False`` would write an
        # explicit off-toggle into the XML rather than nothing.
        run = self.document.add_paragraph().add_run(text)
        if bold:
            run.bold = True
        if italic:
            run.italic = True

    def lines(self, texts: list[str | None]) -> None:
        """One paragraph per text, skipping absent values."""
        for text in texts:
            if text:
                self.line(text)

    def bullets(self, items: list[str]) -> None:
        # A literal hyphen typed into the text, the way a plain-text CV does it.
        for item in items:
            self.line(f"- {self.soft_hyphenated(item)}")

    def date_line(self, planned: PlannedEntry) -> None:
        parts = [part for part in (planned.start, planned.end) if part is not None]
        if not parts:
            return
        if any(_NBSP in part for part in parts):
            self.decisions.injected(_NBSP)
        self.line(" - ".join(parts))

    def experience(self, planned: PlannedEntry[ExperienceEntry]) -> None:
        entry = planned.entry
        self.line(entry.title, bold=True)
        employer_line = (
            entry.employer
            if entry.location is None
            else f"{entry.employer}, {entry.location}"
        )
        self.line(employer_line, italic=True)
        self.date_line(planned)
        self.bullets(entry.bullets)

    def education(self, planned: PlannedEntry[EducationEntry]) -> None:
        entry = planned.entry
        self.line(entry.qualification, bold=True)
        self.line(entry.institution, italic=True)
        self.date_line(planned)
        self.bullets(entry.details)

    # --- Text boxes

    def text_box(self, *, shape_id: str, texts: list[str | None]) -> None:
        """A paragraph holding a text box whose content is one paragraph per
        text, skipping absent values."""
        content = etree.Element(f"{{{_W}}}txbxContent")
        for text in texts:
            if text:
                paragraph = etree.SubElement(content, f"{{{_W}}}p")
                run = etree.SubElement(paragraph, f"{{{_W}}}r")
                t = etree.SubElement(run, f"{{{_W}}}t")
                t.text = text
                t.set(_XML_SPACE, "preserve")
        xml = _TEXT_BOX.format(
            shape_type="" if self._shape_type_declared else _SHAPE_TYPE,
            id=shape_id,
            content=etree.tostring(content, encoding="unicode"),
        )
        self._shape_type_declared = True
        self.document.add_paragraph()._p.append(parse_xml(xml))
