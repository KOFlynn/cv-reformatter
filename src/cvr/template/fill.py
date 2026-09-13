"""Fills the template with content through docxtpl.

The context mirrors ``CVContent`` plus ``unplaced``; nothing is derived or
reworded on the way in. Every rendered string is one of the caller's own
strings, so the invariant that no wording is ever changed holds here by
construction: this module has no text of its own.
"""

from io import BytesIO

from docxtpl import DocxTemplate

from cvr.models import CVContent
from cvr.template.paths import TEMPLATE_PATH

__all__ = ["fill"]


def fill(content: CVContent, unplaced: list[str]) -> bytes:
    """The template rendered with ``content`` and the review appendix, as ``.docx`` bytes.

    Autoescape is on so that ``&`` and ``<`` in a candidate's text land in the
    document as themselves rather than corrupting the XML.
    """
    document = DocxTemplate(TEMPLATE_PATH)
    document.render(
        {**content.model_dump(), "unplaced": list(unplaced)}, autoescape=True
    )
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
