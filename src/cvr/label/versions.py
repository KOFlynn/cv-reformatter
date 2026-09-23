"""The prompt file, loaded once at import, and the two hand-bumped version
labels plus the content hash that ties them to what was actually sent.
``PROMPT_VERSION`` bumps when ``prompt.md`` changes meaning; ``SCHEMA_VERSION``
bumps when the labelling schema's shape changes. ``CONTENT_HASH`` is
computed from the prompt text and the JSON schema, so a bumped version label
with no text change, or a text change with no version bump, shows up as a
hash mismatch in a diff rather than going unnoticed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cvr.models import Labelling

__all__ = [
    "CONTENT_HASH",
    "LABELLING_JSON_SCHEMA",
    "PROMPT_TEXT",
    "PROMPT_VERSION",
    "SCHEMA_VERSION",
]

# Hand-bumped: change PROMPT_VERSION when prompt.md's instructions change in
# a way that could change the model's answers; change SCHEMA_VERSION when
# the labelling schema's shape changes.
PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

PROMPT_TEXT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")

# The schema sent to the provider is ticket 03's labelling-result type,
# unmodified: a reference tree, a mandatory quote on every leaf, and the
# closed rule enumeration. It is asserted strict-compatible by
# tests/models/test_labelling.py.
LABELLING_JSON_SCHEMA = Labelling.model_json_schema()

CONTENT_HASH = hashlib.sha256(
    (PROMPT_TEXT + json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)).encode("utf-8")
).hexdigest()[:16]
