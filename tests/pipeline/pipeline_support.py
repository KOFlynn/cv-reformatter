"""The generated documents, and every Phase 0 metric fed from a real run.

The scoring is the eval runner's (``cvr.eval.run.score``) and the document
loading too (``cvr.eval.run.documents``); ticket 06 wired both here first,
and ticket 09 moved them into the runner. This module keeps the names the
pipeline tests import, plus the list of every generated document's stem.
"""

from cvr.eval.run.documents import Document, document, generated_stems
from cvr.eval.run.score import Scores, score, to_cv_content, units

__all__ = [
    "GENERATED",
    "Document",
    "Scores",
    "document",
    "score",
    "to_cv_content",
    "units",
]

GENERATED: list[str] = generated_stems()
assert len(GENERATED) == 48, f"expected 48 generated documents, found {len(GENERATED)}"
