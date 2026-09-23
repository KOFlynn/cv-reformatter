"""The prompt loads at import, and its version, the schema version and a
content hash of both are exported so a bumped label with no text change,
or the reverse, shows in a diff."""

import hashlib
import json

from cvr.label.versions import (
    CONTENT_HASH,
    LABELLING_JSON_SCHEMA,
    PROMPT_TEXT,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from cvr.models import Labelling


def test_prompt_loads_at_import_and_carries_its_rules():
    assert "verbatim" in PROMPT_TEXT
    assert "RM_REFEREE" in PROMPT_TEXT
    assert "RM_HEADING" in PROMPT_TEXT
    assert PROMPT_VERSION
    assert SCHEMA_VERSION


def test_schema_is_the_labelling_model_schema():
    assert LABELLING_JSON_SCHEMA == Labelling.model_json_schema()


def test_content_hash_covers_prompt_and_schema():
    expected = hashlib.sha256(
        (PROMPT_TEXT + json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)).encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    assert CONTENT_HASH == expected


def test_content_hash_changes_if_prompt_or_schema_would_change():
    other_hash = hashlib.sha256(
        (PROMPT_TEXT + "x" + json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)).encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    assert other_hash != CONTENT_HASH
