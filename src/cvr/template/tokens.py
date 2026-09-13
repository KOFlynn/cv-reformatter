"""Extracts the template's own fixed text at run time, minus its Jinja tags.

The eval whitelist (``added_tokens``' ``template`` argument and
``provenance_violations``' ``template_units``) must track the template, so it is read from
the built document every time and never typed into a list. The walk is
deliberately structure-blind: every ``w:p`` in every ``word/*.xml`` part,
including headers and footers, joined per paragraph so a tag split across
runs would still be recognised as one tag.
"""

import io
import re
import zipfile
from pathlib import Path

from lxml import etree

from cvr.template.paths import TEMPLATE_PATH
from cvr.text import tokenise

__all__ = ["template_text", "template_tokens"]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Jinja statements ({% %} and docxtpl's {%p %}), expressions and comments.
_TAG = re.compile(r"{%.*?%}|{{.*?}}|{#.*?#}", re.DOTALL)


def template_text(template: Path = TEMPLATE_PATH) -> list[str]:
    """Each paragraph's fixed text with tags removed, in document order,
    blanks dropped. Punctuation-only fragments (the date dash, the employer
    comma) are kept: they are template text too."""
    texts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(template.read_bytes())) as package:
        for name in sorted(package.namelist()):
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            root = etree.fromstring(package.read(name))
            for paragraph in root.iter(f"{_W}p"):
                raw = "".join(t.text or "" for t in paragraph.iter(f"{_W}t"))
                fixed = _TAG.sub("", raw).strip()
                if fixed:
                    texts.append(fixed)
    return texts


def template_tokens(template: Path = TEMPLATE_PATH) -> list[str]:
    """The fixed text tokenised with the shared ``tokenise``, multiplicity kept."""
    return [token for text in template_text(template) for token in tokenise(text)]
