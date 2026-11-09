"""The API's transform log on standard output: one summary line and one
detail line per block per request, all JSON, all carrying the run id; no
line reaches the 32 KB a Log Analytics field truncates at, for any golden-set
document, the largest included; and no PII canary reaches it. What the lines
hold is ``cvr.runlog``'s, tested in ``tests/runlog/``."""

import json

import pytest
from api_support import AUTH
from fastapi.testclient import TestClient
from log_canaries import CANARIES, canary_document
from oracle import Oracle
from pipeline_support import GENERATED, document

from cvr.api import DOCX_MEDIA_TYPE as DOCX
from cvr.api import RUN_ID_HEADER, create_app
from cvr.golden import LAYOUTS
from cvr.parse import parse
from cvr.runlog import MAX_LINE_BYTES

# The golden-set document with the most blocks, so the most detail lines.
LARGEST = "c11__two-column"


def _logged(stem: str, capsys) -> tuple[str, list[str]]:
    doc = document(stem)
    client = TestClient(create_app(Oracle(doc.candidate, doc.manifest)))
    capsys.readouterr()
    response = client.post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=AUTH
    )
    assert response.status_code == 200
    return response.headers[RUN_ID_HEADER], capsys.readouterr().out.splitlines()


def test_one_summary_line_and_a_line_per_block_all_with_the_run_id(capsys):
    run_id, out = _logged("c04__two-column", capsys)
    lines = [json.loads(line) for line in out]
    assert [line["line"] for line in lines].count("summary") == 1
    assert lines[0]["line"] == "summary"
    blocks = [line for line in lines if line["line"] == "block"]
    assert len(blocks) == lines[0]["blocks"] > 0
    assert all(line["run_id"] == run_id for line in lines)


def _assert_every_line_fits(out: list[str]) -> None:
    assert out
    for line in out:
        assert len(line.encode("utf-8")) < MAX_LINE_BYTES


def test_no_line_reaches_32_kb_for_the_largest_document(capsys):
    _assert_every_line_fits(_logged(LARGEST, capsys)[1])


@pytest.mark.slow
def test_the_largest_document_is_the_one_with_the_most_blocks():
    counts = {stem: len(parse(document(stem).source).blocks) for stem in GENERATED}
    assert max(counts, key=counts.get) == LARGEST


@pytest.mark.slow
@pytest.mark.parametrize("stem", GENERATED)
def test_no_line_reaches_32_kb(stem, capsys):
    _assert_every_line_fits(_logged(stem, capsys)[1])


# --- PII values never reach the log (Phase 2, ticket 05).


def _forms(value: str) -> set[str]:
    squashed = value.replace(" ", "")
    return {value, value.lower(), squashed, squashed.lower()}


@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda layout: layout.name)
def test_no_pii_canary_reaches_the_log_but_content_does(layout, capsys):
    candidate, manifest, source = canary_document(layout)
    client = TestClient(create_app(Oracle(candidate, manifest)))
    capsys.readouterr()
    response = client.post(
        "/reformat", files={"file": ("cv.docx", source, DOCX)}, headers=AUTH
    )
    assert response.status_code == 200
    captured = capsys.readouterr()
    logged = captured.out + captured.err
    squashed = logged.lower().replace(" ", "")
    for canary in CANARIES:
        for form in _forms(canary):
            assert form not in logged, (layout.name, form)
        assert canary.lower().replace(" ", "") not in squashed
    # Positive control: non-PII text is in the block lines (the ledger holds
    # offsets, so the text there is headings removed and the dates' spans).
    lines = [json.loads(line) for line in captured.out.splitlines()]
    block_text = json.dumps(
        [line for line in lines if line["line"] == "block"], ensure_ascii=False
    )
    assert manifest.headings
    for heading in manifest.headings:
        assert heading in block_text
