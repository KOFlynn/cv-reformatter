"""The transform log on standard output: one summary line and one detail line
per block, all JSON, all carrying the run id; together they hold the whole
Run; and no line reaches the 32 KB a Log Analytics field truncates at, for
any golden-set document, the largest included."""

import json

import pytest
from api_support import AUTH
from fastapi.testclient import TestClient
from oracle import Oracle
from pipeline_support import GENERATED, document

from cvr.api import DOCX_MEDIA_TYPE as DOCX
from cvr.api import RUN_ID_HEADER, create_app
from cvr.api.log import MAX_LINE_BYTES, request_lines
from cvr.models import Image, LabelRun, Run
from cvr.parse import parse
from cvr.pipeline import reformat

# The golden-set document with the most blocks, so the most detail lines.
LARGEST = "c11__two-column"

LABEL_RUN = LabelRun(
    config={"model": "oracle"},
    prompt_version="p",
    prompt_hash="ph",
    schema_version="s",
    schema_hash="sh",
    content_hash="ch",
    input_tokens=1,
)


def _logged(stem: str, capsys) -> tuple[str, list[str]]:
    doc = document(stem)
    client = TestClient(create_app(Oracle(doc.candidate, doc.manifest)))
    capsys.readouterr()
    response = client.post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=AUTH
    )
    assert response.status_code == 200
    return response.headers[RUN_ID_HEADER], capsys.readouterr().out.splitlines()


def _reassembled(lines: list[dict]) -> Run:
    """The Run read back out of its log lines."""
    (summary,) = [line for line in lines if line["line"] == "summary"]
    blocks = [line for line in lines if line["line"] == "block"]
    return Run.model_validate(
        {
            "run_id": summary["run_id"],
            "label": summary["label"],
            "label_failed": summary["label_failed"],
            "removals": [
                *summary["images"],
                *(r for block in blocks for r in block["removals"]),
            ],
            "normalisations": [n for block in blocks for n in block["normalisations"]],
            "ledgers": {block["block_id"]: block["ledger"] for block in blocks},
            "residue": [r for block in blocks for r in block["residue"]],
            "date_map": [d for block in blocks for d in block["dates"]],
            "split_map": {p: s for block in blocks for p, s in block["splits"].items()},
        }
    )


def _sorted(run: Run, field: str) -> list[str]:
    """``field`` of ``run`` as sorted JSON, for a comparison blind to order:
    the log groups by block, and the Run keeps tree-walk order."""
    return sorted(
        json.dumps(x, sort_keys=True) for x in run.model_dump(mode="json")[field]
    )


def test_one_summary_line_and_a_line_per_block_all_with_the_run_id(capsys):
    run_id, out = _logged("c04__two-column", capsys)
    lines = [json.loads(line) for line in out]
    assert [line["line"] for line in lines].count("summary") == 1
    assert lines[0]["line"] == "summary"
    blocks = [line for line in lines if line["line"] == "block"]
    assert len(blocks) == lines[0]["blocks"] > 0
    assert all(line["run_id"] == run_id for line in lines)


def test_the_lines_hold_the_whole_run():
    doc = document("c04__two-column")
    _, run = reformat(doc.source, Oracle(doc.candidate, doc.manifest))
    run = run.model_copy(update={"label": LABEL_RUN})
    lines = [json.loads(line) for line in request_lines(run.run_id, 200, run=run)]
    back = _reassembled(lines)
    assert back.run_id == run.run_id
    assert back.label == run.label
    assert back.label_failed == run.label_failed
    assert back.ledgers == run.ledgers
    assert back.split_map == run.split_map
    for field in ("removals", "normalisations", "residue", "date_map"):
        assert _sorted(back, field) == _sorted(run, field), field
    assert any(isinstance(r.subject, Image) for r in back.removals)


def test_a_failed_request_is_one_summary_line_with_the_error():
    (line,) = request_lines("abc", 415, error="not a .docx")
    assert json.loads(line) == {
        "run_id": "abc",
        "line": "summary",
        "status": 415,
        "error": "not a .docx",
    }


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
