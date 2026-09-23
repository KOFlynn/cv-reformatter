"""The label node: parsed blocks in, a labelling result and a ``LabelRun``
out. The only pipeline package that reaches the network; every other node
is pure. Depends on ``models`` and LangChain. ADR-0009.

``RealLabeller`` is a callable from blocks to a labelling result (the
pipeline's labeller seam); construct it once from a ``LabellerConfig`` and
call it per document. ``LabelRun`` (its ``last_run`` after a call) carries
the prompt and schema identity, tokens and cost for the pipeline's ``Run``
(ticket 06) to fold in.
"""

from cvr.label.config import LabellerConfig
from cvr.label.labeller import LabelRun, RealLabeller
from cvr.label.pricing import PRICE_TABLE, PRICE_TABLE_CHECKED
from cvr.label.versions import (
    CONTENT_HASH,
    LABELLING_JSON_SCHEMA,
    PROMPT_TEXT,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)

__all__ = [
    "CONTENT_HASH",
    "LABELLING_JSON_SCHEMA",
    "PRICE_TABLE",
    "PRICE_TABLE_CHECKED",
    "PROMPT_TEXT",
    "PROMPT_VERSION",
    "SCHEMA_VERSION",
    "LabelRun",
    "LabellerConfig",
    "RealLabeller",
]
