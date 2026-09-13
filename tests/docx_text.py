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
    data = document if isinstance(document, bytes) else document.read_bytes()
    texts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        for name in sorted(package.namelist()):
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            root = etree.fromstring(package.read(name))
            texts.extend(element.text or "" for element in root.iter(W_T))
    return texts
