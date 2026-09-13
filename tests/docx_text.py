"""Deliberately dumb text extraction for document tests: generated sources and
the rendered template alike.

Walks every ``w:t`` element in every ``word/*.xml`` part of a ``.docx``: body,
tables, headers, footers and text boxes alike, with no structure and no
reading order. Being this dumb is the point: a Layout or the template can put
text anywhere python-docx can or cannot reach and the test still sees it.
"""

import io
import zipfile
from pathlib import Path

from lxml import etree

W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


def all_text(document: Path | bytes) -> list[str]:
    """The text of every ``w:t`` in the document, one item per element.

    Parts are visited in name order and elements in document order, so the
    result is deterministic; it is not the document's reading order.
    """
    return [text for texts in text_by_part(document).values() for text in texts]


def image_count(document: Path | bytes) -> int:
    """How many image parts the package carries, whatever references them."""
    data = document if isinstance(document, bytes) else document.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return sum(1 for name in package.namelist() if name.startswith("word/media/"))


def text_by_part(document: Path | bytes) -> dict[str, list[str]]:
    """``all_text`` split by part: package part name (``word/document.xml``,
    ``word/header1.xml``, ...) to the text of every ``w:t`` in it, in element
    order. As dumb as ``all_text``; it only remembers which part a text came from.
    """
    data = document if isinstance(document, bytes) else document.read_bytes()
    parts: dict[str, list[str]] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        for name in sorted(package.namelist()):
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            root = etree.fromstring(package.read(name))
            parts[name] = [element.text or "" for element in root.iter(W_T)]
    return parts
