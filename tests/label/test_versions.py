"""The prompt loads at import, and the prompt and schema are each checked at
import against the version and hash recorded in ``versions.json``, so a
change without a version bump fails loudly, naming what changed."""

import hashlib
import json

import pytest

from cvr.label.versions import (
    CONTENT_HASH,
    LABELLING_JSON_SCHEMA,
    PROMPT_HASH,
    PROMPT_TEXT,
    PROMPT_VERSION,
    SCHEMA_HASH,
    SCHEMA_VERSION,
    VERSIONS_FILE,
    VersionMismatch,
    check_versions,
)
from cvr.models import Labelling

RECORDED = {
    "prompt": {"version": "1.0.0", "hash": "aaaa"},
    "schema": {"version": "2.1.0", "hash": "bbbb"},
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def test_prompt_loads_at_import_and_carries_its_rules():
    assert "verbatim" in PROMPT_TEXT
    assert "RM_REFEREE" in PROMPT_TEXT
    assert "RM_HEADING" in PROMPT_TEXT


def test_schema_is_the_labelling_model_schema():
    assert LABELLING_JSON_SCHEMA == Labelling.model_json_schema()


def test_hashes_cover_the_prompt_the_schema_and_both():
    schema_text = json.dumps(LABELLING_JSON_SCHEMA, sort_keys=True)
    assert PROMPT_HASH == _hash(PROMPT_TEXT)
    assert SCHEMA_HASH == _hash(schema_text)
    assert CONTENT_HASH == _hash(PROMPT_TEXT + schema_text)


def test_versions_come_from_the_committed_file_and_match_it():
    recorded = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    assert PROMPT_VERSION == recorded["prompt"]["version"]
    assert SCHEMA_VERSION == recorded["schema"]["version"]
    assert recorded["prompt"]["hash"] == PROMPT_HASH
    assert recorded["schema"]["hash"] == SCHEMA_HASH


def test_matching_hashes_pass():
    check_versions(RECORDED, {"prompt": "aaaa", "schema": "bbbb"})


def test_a_changed_prompt_names_the_prompt_and_the_fix():
    with pytest.raises(VersionMismatch) as raised:
        check_versions(RECORDED, {"prompt": "cccc", "schema": "bbbb"})
    message = str(raised.value)
    assert "prompt.md has changed since prompt version 1.0.0" in message
    assert "Bump the prompt version in src/cvr/label/versions.json" in message
    assert "set its hash to cccc" in message
    assert "eval run" in message
    assert "schema version" not in message


def test_a_changed_schema_names_the_schema_and_the_fix():
    with pytest.raises(VersionMismatch) as raised:
        check_versions(RECORDED, {"prompt": "aaaa", "schema": "dddd"})
    message = str(raised.value)
    assert "labelling schema (cvr.models.Labelling) has changed" in message
    assert "since schema version 2.1.0" in message
    assert "set its hash to dddd" in message
    assert "prompt.md" not in message


def test_both_changed_names_both():
    with pytest.raises(VersionMismatch) as raised:
        check_versions(RECORDED, {"prompt": "cccc", "schema": "dddd"})
    message = str(raised.value)
    assert "prompt.md has changed" in message
    assert "labelling schema (cvr.models.Labelling) has changed" in message
