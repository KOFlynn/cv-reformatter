"""Blocks in reading order, with addresses for ids.

The walk is over the raw XML for everything with text in it: python-docx
neither exposes text boxes nor gives a table cell's address (its ``row.cells``
repeats a merged cell), so one walker reads paragraphs, tables and text boxes
alike, and python-docx is used only to open the package and to find each
section's header and footer parts by type.

Order: body children (paragraphs and tables share the numbering), each with
any text box anchored in it straight after; then for each section its headers
(default, first, even) and footers (default, first, even). A text box's
position is its anchor's, an approximation of where Word draws it.

Ids are addresses: ``body:N`` is the N-th child of ``w:body``;
``table:N:rR:cC:P`` the P-th child of the C-th ``w:tc`` of the R-th ``w:tr``
of body child N; ``header:S:T:P`` / ``footer:S:T:P`` the P-th child of the
header or footer of type T (``default | first | even``) in section S;
``textbox:N:B:P`` the P-th paragraph of the B-th text box found in body child
N. Every index counts every child, so an empty or image-only paragraph keeps
its number and the ids are the same on every parse of the same file.
"""

from collections.abc import Iterator

from docx.document import Document as DocumentType
from lxml import etree

from cvr.models import BlockKind, Normalisation, NormalisationRule, SourceBlock
from cvr.text import CONFUSABLES

__all__ = ["walk"]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
W_P, W_TBL, W_TR, W_TC, W_TCPR = (
    f"{_W}p",
    f"{_W}tbl",
    f"{_W}tr",
    f"{_W}tc",
    f"{_W}tcPr",
)
W_T, W_TAB, W_BR, W_CR = f"{_W}t", f"{_W}tab", f"{_W}br", f"{_W}cr"
W_TXBX_CONTENT = f"{_W}txbxContent"
# Subtrees a paragraph's text never descends into: its properties (a tab stop
# is a ``w:tab`` too), a text box (read separately, at the anchor), and the
# fallback half of an alternate-content pair (the same text again, for old Word).
_NOT_TEXT = frozenset({f"{_W}pPr", f"{_W}rPr", W_TXBX_CONTENT, f"{_MC}Fallback"})

# The confusable table's deletion rows: what NORM_INVISIBLE strips.
_INVISIBLE = frozenset(char for char, out in CONFUSABLES.items() if out == "")

# The header and footer types in the order they are emitted, with python-docx's
# accessor for each on a Section.
_HEADER_TYPES = (
    ("default", "header"),
    ("first", "first_page_header"),
    ("even", "even_page_header"),
)
_FOOTER_TYPES = (
    ("default", "footer"),
    ("first", "first_page_footer"),
    ("even", "even_page_footer"),
)


def walk(document: DocumentType) -> tuple[list[SourceBlock], list[Normalisation]]:
    """Every block of the document in reading order, and one NORM_INVISIBLE
    event for each block that had invisible characters stripped."""
    blocks: list[SourceBlock] = []
    events: list[Normalisation] = []
    for kind, block_id, element in _addresses(document):
        text, stripped = _strip_invisible(_text(element))
        if not text.strip():
            continue  # a gap: an empty or image-only paragraph keeps its index
        blocks.append(SourceBlock(id=block_id, text=text, kind=kind))
        if stripped:
            events.append(
                Normalisation(
                    rule=NormalisationRule.INVISIBLE,
                    block_id=block_id,
                    characters=stripped,
                )
            )
    return blocks, events


def _addresses(
    document: DocumentType,
) -> Iterator[tuple[BlockKind, str, etree._Element]]:
    """Each paragraph element with its kind and id, in reading order."""
    for n, child in enumerate(document.element.body):
        if child.tag == W_P:
            yield "body", f"body:{n}", child
        elif child.tag == W_TBL:
            yield from _table(n, child)
        for b, box in enumerate(_text_boxes(child)):
            for p, paragraph in enumerate(box):
                if paragraph.tag == W_P:
                    yield "textbox", f"textbox:{n}:{b}:{p}", paragraph
    for s, section in enumerate(document.sections):
        for kind, types in (("header", _HEADER_TYPES), ("footer", _FOOTER_TYPES)):
            for type_name, accessor in types:
                yield from _header_footer(
                    kind, s, type_name, getattr(section, accessor)
                )


def _table(
    n: int, table: etree._Element
) -> Iterator[tuple[BlockKind, str, etree._Element]]:
    rows = [row for row in table if row.tag == W_TR]
    for r, row in enumerate(rows):
        cells = [cell for cell in row if cell.tag == W_TC]
        for c, cell in enumerate(cells):
            # A cell's first child is its properties, not content; P counts
            # from the first paragraph as it does in the body and a header.
            content = [child for child in cell if child.tag != W_TCPR]
            for p, child in enumerate(content):
                if child.tag == W_P:
                    yield "table", f"table:{n}:r{r}:c{c}:{p}", child


def _header_footer(
    kind: BlockKind, s: int, type_name: str, part
) -> Iterator[tuple[BlockKind, str, etree._Element]]:
    """``part`` is python-docx's header or footer proxy for one section."""
    # A linked header has no part of its own: its content is the previous
    # section's, already read, or nothing. Reaching for its element through
    # python-docx would add an empty definition to the document, so ask first.
    if part.is_linked_to_previous:
        return
    for p, child in enumerate(part._element):
        if child.tag == W_P:
            yield kind, f"{kind}:{s}:{type_name}:{p}", child


def _text_boxes(element: etree._Element) -> Iterator[etree._Element]:
    """Every ``w:txbxContent`` under ``element`` in document order, skipping the
    fallback copy of an alternate-content pair."""
    for child in element:
        if child.tag == W_TXBX_CONTENT:
            yield child
        elif child.tag != f"{_MC}Fallback":
            yield from _text_boxes(child)


def _text(element: etree._Element) -> str:
    """The text of a paragraph as python-docx reads it (``w:t`` text, a tab
    for ``w:tab``, a newline for ``w:br`` and ``w:cr``), through hyperlinks and
    other wrappers, never into a text box or the paragraph's properties."""
    parts: list[str] = []
    for child in element:
        if child.tag in _NOT_TEXT:
            continue
        if child.tag == W_T:
            parts.append(child.text or "")
        elif child.tag == W_TAB:
            parts.append("\t")
        elif child.tag in (W_BR, W_CR):
            parts.append("\n")
        else:
            parts.append(_text(child))
    return "".join(parts)


def _strip_invisible(text: str) -> tuple[str, list[str]]:
    """The text without the confusable table's deletion rows, and the
    characters taken out, in source order."""
    stripped = [char for char in text if char in _INVISIBLE]
    if not stripped:
        return text, []
    return "".join(char for char in text if char not in _INVISIBLE), stripped
