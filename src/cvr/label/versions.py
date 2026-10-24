"""The prompt files, loaded once at import, and the prompt and schema versions
checked against what was recorded for them.

``versions.json`` beside this module records, for each of four artefacts (the
prompt, the labelling schema, the retry prompt and the additions schema), the
current version and the hash of the text that version stands for. Import
computes the hashes afresh and compares: if ``prompt.md``, ``retry_prompt.md``
or either schema has changed without its entry being updated, import fails
with :class:`VersionMismatch`, naming which one changed and what to do. Git
holds the diffs; this makes sure the version number keeps up with them.
``CONTENT_HASH`` covers all four together, for the eval cache key.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cvr.models import Additions, Labelling

__all__ = [
    "ADDITIONS_HASH",
    "ADDITIONS_JSON_SCHEMA",
    "ADDITIONS_VERSION",
    "CONTENT_HASH",
    "LABELLING_JSON_SCHEMA",
    "PROMPT_HASH",
    "PROMPT_TEXT",
    "PROMPT_VERSION",
    "RETRY_HASH",
    "RETRY_TEXT",
    "RETRY_VERSION",
    "SCHEMA_HASH",
    "SCHEMA_VERSION",
    "VERSIONS_FILE",
    "VersionMismatch",
    "check_versions",
]

_HERE = Path(__file__).parent
VERSIONS_FILE = _HERE / "versions.json"

# read_text translates line endings, so a CRLF checkout hashes the same as LF.
PROMPT_TEXT = (_HERE / "prompt.md").read_text(encoding="utf-8")
# The retry prompt (ticket 12): the blocks, the first answer and the feedback.
RETRY_TEXT = (_HERE / "retry_prompt.md").read_text(encoding="utf-8")

# The schema sent to the provider is ticket 03's labelling-result type,
# unmodified: a reference tree, a mandatory quote on every leaf, and the
# closed rule enumeration. It is asserted strict-compatible by
# tests/models/test_labelling.py.
LABELLING_JSON_SCHEMA = Labelling.model_json_schema()
_SCHEMA_TEXT = json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)

# A retry's schema: path-addressed additions to the first answer.
ADDITIONS_JSON_SCHEMA = Additions.model_json_schema()
_ADDITIONS_TEXT = json.dumps(ADDITIONS_JSON_SCHEMA, sort_keys=True)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


PROMPT_HASH = _hash(PROMPT_TEXT)
SCHEMA_HASH = _hash(_SCHEMA_TEXT)
RETRY_HASH = _hash(RETRY_TEXT)
ADDITIONS_HASH = _hash(_ADDITIONS_TEXT)
CONTENT_HASH = _hash(PROMPT_TEXT + _SCHEMA_TEXT + RETRY_TEXT + _ADDITIONS_TEXT)


class VersionMismatch(RuntimeError):
    """A prompt or a schema changed without its version being bumped."""


_WHAT = {
    "prompt": "src/cvr/label/prompt.md",
    "schema": "the labelling schema (cvr.models.Labelling)",
    "retry_prompt": "src/cvr/label/retry_prompt.md",
    "additions_schema": "the additions schema (cvr.models.Additions)",
}


def check_versions(recorded: dict[str, Any], current: dict[str, str]) -> None:
    """Raise :class:`VersionMismatch` if a current hash differs from the one
    recorded for its version, one line per thing that changed. Checks the
    names in ``current``."""
    problems = [
        f"{_WHAT[name]} has changed since {name} version "
        f"{recorded[name]['version']} was recorded (recorded hash "
        f"{recorded[name]['hash']}, current hash {current[name]}). Bump the "
        f"{name} version in src/cvr/label/versions.json and set its hash to "
        f"{current[name]}."
        for name in current
        if recorded[name]["hash"] != current[name]
    ]
    if problems:
        raise VersionMismatch(
            "\n".join(problems)
            + "\nA prompt or schema change must be followed by an eval run."
        )


_RECORDED = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
check_versions(
    _RECORDED,
    {
        "prompt": PROMPT_HASH,
        "schema": SCHEMA_HASH,
        "retry_prompt": RETRY_HASH,
        "additions_schema": ADDITIONS_HASH,
    },
)

PROMPT_VERSION: str = _RECORDED["prompt"]["version"]
SCHEMA_VERSION: str = _RECORDED["schema"]["version"]
RETRY_VERSION: str = _RECORDED["retry_prompt"]["version"]
ADDITIONS_VERSION: str = _RECORDED["additions_schema"]["version"]
