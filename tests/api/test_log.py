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
from cvr.golden import CANDIDATES_DIR, LAYOUTS, load_candidate
from cvr.models import Image, LabelRun, Removal, RemovalRule, Residue, Run, Span
from cvr.parse import parse
from cvr.pipeline import reformat

# The golden-set document with the most blocks, so the most detail lines.
LARGEST = "c11__two-column"

STRIPPED = "~"

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


def _unstrip(subject: dict) -> None:
    """Give a stripped span (no text, a length and a class) back a text of the
    right length, so the Run validates: the log never holds the real one."""
    if "text" not in subject:
        subject["text"] = STRIPPED * subject.pop("length")
        del subject["class"]


def _blanked(run: Run) -> Run:
    """``run`` as the log is expected to hold it: PII removals, and residue
    overlapping one, with their text blanked to ``STRIPPED`` characters."""
    pii = [
        r.subject
        for r in run.removals
        if isinstance(r.subject, Span) and r.rule != RemovalRule.HEADING
    ]

    def blank(span: Span) -> Span:
        return span.model_copy(update={"text": STRIPPED * len(span.text)})

    def hit(span: Span) -> bool:
        return any(
            p.block_id == span.block_id and span.start < p.end and p.start < span.end
            for p in pii
        )

    return run.model_copy(
        update={
            "removals": [
                r.model_copy(update={"subject": blank(r.subject)})
                if r.subject in pii
                else r
                for r in run.removals
            ],
            "residue": [
                r.model_copy(update={"span": blank(r.span)}) if hit(r.span) else r
                for r in run.residue
            ],
        }
    )


def _reassembled(lines: list[dict]) -> Run:
    """The Run read back out of its log lines."""
    (summary,) = [line for line in lines if line["line"] == "summary"]
    blocks = [line for line in lines if line["line"] == "block"]
    for block in blocks:
        for removal in block["removals"]:
            _unstrip(removal["subject"])
        for residue in block["residue"]:
            _unstrip(residue["span"])
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
    run = _blanked(run)
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


# --- PII values never reach the log (Phase 2, ticket 05).

CANARY_EMAIL = "Canary-7F3@example.invalid"
CANARY_PHONE = "+44 7391 658 204"
CANARY_ADDRESS = "17 Zebulon Quay"
CANARIES = (CANARY_EMAIL, CANARY_PHONE, CANARY_ADDRESS)


def _canary_document(layout):
    """Candidate c04 with its email, phone and first address line replaced by
    canaries, rendered through ``layout``; built here, nothing in the fixtures
    changes."""
    base = load_candidate(CANDIDATES_DIR / "c04.json")
    pii = base.pii.model_copy(
        update={
            "email": CANARY_EMAIL,
            "phone": CANARY_PHONE,
            "address": [CANARY_ADDRESS, *base.pii.address[1:]],
        }
    )
    candidate = base.model_copy(update={"pii": pii})
    generated = layout.generate(candidate)
    return candidate, generated.manifest, generated.document


def _forms(value: str) -> set[str]:
    squashed = value.replace(" ", "")
    return {value, value.lower(), squashed, squashed.lower()}


@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda layout: layout.name)
def test_no_pii_canary_reaches_the_log_but_content_does(layout, capsys):
    candidate, manifest, source = _canary_document(layout)
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


def _run_of(layout) -> Run:
    candidate, manifest, source = _canary_document(layout)
    return reformat(source, Oracle(candidate, manifest))[1]


def _logged_removals(run: Run) -> list[dict]:
    lines = [json.loads(line) for line in request_lines(run.run_id, 200, run=run)]
    return [
        r
        for line in lines
        if line["line"] == "block"
        for r in line.get("removals", [])
        if isinstance(r, dict)
    ]


def test_a_stripped_removal_keeps_rule_block_offsets_length_and_class():
    run = _run_of(LAYOUTS[0])
    originals = {
        r.rule: r.subject
        for r in run.removals
        if isinstance(r.subject, Span)
        and r.rule in (RemovalRule.EMAIL, RemovalRule.PHONE)
    }
    logged = {RemovalRule(r["rule"]): r["subject"] for r in _logged_removals(run)}
    for rule, shape in (
        (RemovalRule.EMAIL, "aaaaaa#9a9#aaaaaaa#aaaaaaa"),
        (RemovalRule.PHONE, "#99_9999_999_999"),
    ):
        span = originals[rule]
        assert logged[rule] == {
            "block_id": span.block_id,
            "start": span.start,
            "end": span.end,
            "length": span.end - span.start,
            "class": shape,
        }


def test_headings_removed_under_rm_heading_keep_their_text():
    run = _run_of(LAYOUTS[0])
    headings = {
        r.subject.text
        for r in run.removals
        if r.rule == "RM_HEADING" and isinstance(r.subject, Span)
    }
    assert headings
    logged = {
        r["subject"]["text"] for r in _logged_removals(run) if r["rule"] == "RM_HEADING"
    }
    assert logged == headings


def test_the_run_still_holds_the_removal_text():
    run = _run_of(LAYOUTS[0])
    request_lines(run.run_id, 200, run=run)
    texts = {r.subject.text for r in run.removals if isinstance(r.subject, Span)}
    assert CANARY_EMAIL in texts
    assert CANARY_PHONE in texts


def test_residue_overlapping_a_pii_removal_is_stripped():
    run = Run(
        run_id="r",
        removals=[
            Removal(
                rule=RemovalRule.EMAIL,
                subject=Span(block_id="body:0", start=3, end=8, text="lo wo"),
            )
        ],
        residue=[
            Residue(
                span=Span(block_id="body:0", start=0, end=5, text="hello"),
                separator=False,
            ),
            Residue(
                span=Span(block_id="body:1", start=0, end=5, text="other"),
                separator=False,
            ),
        ],
    )
    out = "".join(request_lines("r", 200, run=run))
    assert "hello" not in out and "lo wo" not in out
    assert "other" in out


def test_an_error_field_is_stripped_of_pii_shaped_text():
    (line,) = request_lines(
        "abc", 500, error=f"ValueError: bad {CANARY_EMAIL} and {CANARY_PHONE}"
    )
    assert "example.invalid" not in line
    assert "7391" not in line
    assert json.loads(line)["error"].startswith("ValueError: bad ")
