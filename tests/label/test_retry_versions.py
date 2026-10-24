"""The retry prompt and the additions schema are versioned like the first
prompt and schema (ticket 12): recorded in ``versions.json``, checked at
import, covered by the content hash."""

import json

import pytest

from cvr.label.versions import (
    ADDITIONS_HASH,
    ADDITIONS_VERSION,
    PROMPT_HASH,
    PROMPT_VERSION,
    RETRY_HASH,
    RETRY_TEXT,
    RETRY_VERSION,
    SCHEMA_HASH,
    SCHEMA_VERSION,
    VERSIONS_FILE,
    VersionMismatch,
    check_versions,
)

RECORDED = {
    "prompt": {"version": "1.0.0", "hash": "aaaa"},
    "schema": {"version": "2.1.0", "hash": "bbbb"},
    "retry_prompt": {"version": "1.0.0", "hash": "eeee"},
    "additions_schema": {"version": "1.0.0", "hash": "ffff"},
}
CURRENT = {
    "prompt": "aaaa",
    "schema": "bbbb",
    "retry_prompt": "eeee",
    "additions_schema": "ffff",
}


def test_the_retry_entries_come_from_the_committed_file_and_match_it():
    recorded = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    assert RETRY_VERSION == recorded["retry_prompt"]["version"]
    assert ADDITIONS_VERSION == recorded["additions_schema"]["version"]
    assert recorded["retry_prompt"]["hash"] == RETRY_HASH
    assert recorded["additions_schema"]["hash"] == ADDITIONS_HASH


def test_the_first_prompt_and_schema_versions_are_unchanged():
    assert PROMPT_VERSION == "1.3.0"
    assert SCHEMA_VERSION == "1.0.0"
    assert PROMPT_HASH == "f326caf4f478e95d"
    assert SCHEMA_HASH == "3ee02723787bc1ee"


def test_the_retry_prompt_carries_its_rules():
    assert "verbatim" in RETRY_TEXT
    assert "never write" in RETRY_TEXT.lower()
    assert "experience[i].bullets" in RETRY_TEXT


def test_four_matching_hashes_pass():
    check_versions(RECORDED, CURRENT)


def test_a_changed_retry_prompt_names_the_file_and_the_fix():
    with pytest.raises(VersionMismatch) as raised:
        check_versions(RECORDED, {**CURRENT, "retry_prompt": "cccc"})
    message = str(raised.value)
    assert "retry_prompt.md has changed since retry_prompt version 1.0.0" in message
    assert "Bump the retry_prompt version in src/cvr/label/versions.json" in message
    assert "set its hash to cccc" in message
    assert "additions" not in message


def test_a_changed_additions_schema_names_the_schema_and_the_fix():
    with pytest.raises(VersionMismatch) as raised:
        check_versions(RECORDED, {**CURRENT, "additions_schema": "dddd"})
    message = str(raised.value)
    assert "additions schema (cvr.models.Additions) has changed" in message
    assert "since additions_schema version 1.0.0" in message
    assert "Bump the additions_schema version" in message
    assert "set its hash to dddd" in message
    assert "retry_prompt" not in message
