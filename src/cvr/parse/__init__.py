"""The parse node: a source document in, ordered ``SourceBlock``s out, with
nothing lost. Depends on ``text`` and ``models`` only.

Body paragraphs and tables in body order, text boxes at their anchor's
position, then each section's headers and footers; ids are addresses in the
file (see ``blocks``). Invisible characters are stripped here, under
NORM_INVISIBLE, logged per block, the pre-strip text discarded. Every
embedded image is collected by content hash and removed under RM_PHOTO here,
so the LLM never sees one and never gets a vote on it.
"""

import io
from dataclasses import dataclass, field

from docx import Document

from cvr.models import Image, Normalisation, Removal, RemovalRule, SourceBlock
from cvr.parse.blocks import walk
from cvr.parse.images import collect

__all__ = ["ParsedDocument", "parse"]


@dataclass(frozen=True)
class ParsedDocument:
    """What the parse node hands on: the blocks in reading order, the images,
    the RM_PHOTO removal of each, and the NORM_INVISIBLE events."""

    blocks: list[SourceBlock]
    images: list[Image] = field(default_factory=list)
    removals: list[Removal] = field(default_factory=list)
    normalisations: list[Normalisation] = field(default_factory=list)


def parse(data: bytes) -> ParsedDocument:
    """Parse the bytes of a ``.docx``."""
    blocks, normalisations = walk(Document(io.BytesIO(data)))
    images = collect(data)
    return ParsedDocument(
        blocks=blocks,
        images=images,
        removals=[Removal(rule=RemovalRule.PHOTO, subject=image) for image in images],
        normalisations=normalisations,
    )
