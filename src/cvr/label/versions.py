"""The prompt file, loaded once at import, and the prompt and schema versions
checked against what was recorded for them.

``versions.json`` beside this module records, for the prompt and for the
labelling schema separately, the current version and the hash of the text
that version stands for. Import computes both hashes afresh and compares:
if ``prompt.md`` or the ``Labelling`` schema has changed without its entry
being updated, import fails with :class:`VersionMismatch`, naming which one
changed and what to do. Git holds the diffs; this makes sure the version
number keeps up with them. ``CONTENT_HASH`` covers both together, for the
eval cache key.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cvr.models import Labelling

__all__ = [
    "CONTENT_HASH",
    "LABELLING_JSON_SCHEMA",
    "PROMPT_HASH",
    "PROMPT_TEXT",
    "PROMPT_VERSION",
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

# The schema sent to the provider is ticket 03's labelling-result type,
# unmodified: a reference tree, a mandatory quote on every leaf, and the
# closed rule enumeration. It is asserted strict-compatible by
# tests/models/test_labelling.py.
LABELLING_JSON_SCHEMA = Labelling.model_json_schema()
_SCHEMA_TEXT = json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


PROMPT_HASH = _hash(PROMPT_TEXT)
SCHEMA_HASH = _hash(_SCHEMA_TEXT)
CONTENT_HASH = _hash(PROMPT_TEXT + _SCHEMA_TEXT)


class VersionMismatch(RuntimeError):
    """The prompt or the schema changed without its version being bumped."""


_WHAT = {
    "prompt": "src/cvr/label/prompt.md",
    "schema": "the labelling schema (cvr.models.Labelling)",
}


def check_versions(recorded: dict[str, Any], current: dict[str, str]) -> None:
    """Raise :class:`VersionMismatch` if a current hash differs from the one
    recorded for its version, one line per thing that changed."""
    problems = [
        f"{_WHAT[name]} has changed since {name} version "
        f"{recorded[name]['version']} was recorded (recorded hash "
        f"{recorded[name]['hash']}, current hash {current[name]}). Bump the "
        f"{name} version in src/cvr/label/versions.json and set its hash to "
        f"{current[name]}."
        for name in ("prompt", "schema")
        if recorded[name]["hash"] != current[name]
    ]
    if problems:
        raise VersionMismatch(
            "\n".join(problems)
            + "\nA prompt or schema change must be followed by an eval run."
        )


_RECORDED = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
check_versions(_RECORDED, {"prompt": PROMPT_HASH, "schema": SCHEMA_HASH})

PROMPT_VERSION: str = _RECORDED["prompt"]["version"]
SCHEMA_VERSION: str = _RECORDED["schema"]["version"]
