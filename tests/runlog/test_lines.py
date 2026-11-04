"""The transform log's lines: one summary line and one detail line per block,
all JSON, all carrying the run id; together they hold the whole Run, with
PII values stripped (Phase 2, ticket 05). The API's own log, written through
these, is tested in ``tests/api/test_log.py``."""

import json

from log_canaries import CANARY_EMAIL, CANARY_PHONE, canary_document
from oracle import Oracle
from pipeline_support import document

from cvr.golden import LAYOUTS
from cvr.models import (
    Image,
    LabelRun,
    Removal,
    RemovalRule,
    Residue,
    RetryRejection,
    RetryRun,
    Run,
    Span,
)
from cvr.models.feedback import Feedback, UnlocatableHint, UnplacedRun
from cvr.pipeline import reformat
from cvr.runlog import request_lines

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


def test_a_runs_retries_add_a_count_and_summed_cost_and_tokens_and_no_text():
    """Ticket 14: the summary line states the retry count and sums cost and
    tokens over the first attempt and every retry; the block lines are the same
    as without retries and the retry records themselves (paths, offsets) are
    not logged."""
    doc = document("c04__two-column")
    _, run = reformat(doc.source, Oracle(doc.candidate, doc.manifest))
    first = LABEL_RUN.model_copy(
        update={"input_tokens": 100, "output_tokens": 10, "cost_usd": 0.5}
    )
    second = LABEL_RUN.model_copy(
        update={"input_tokens": 30, "output_tokens": 7, "cost_usd": 0.25}
    )

    def retry(label):
        return RetryRun(
            label=label,
            feedback=Feedback(
                unplaced=[UnplacedRun(block_id="body:0", start=0, end=4)],
                unlocatable=[UnlocatableHint(path="skills[0]", block_id="body:0")],
            ),
            rejections=[
                RetryRejection(
                    path="skills[0]", block_id="body:0", reason="unlocatable"
                )
            ],
            unplaced_chars=4,
        )

    plain_run = run.model_copy(update={"label": first})
    # an outage on the last retry has no record and adds nothing to the sums
    retried = plain_run.model_copy(update={"retries": [retry(second), retry(None)]})
    plain = [json.loads(line) for line in request_lines(run.run_id, 200, run=plain_run)]
    logged = [json.loads(line) for line in request_lines(run.run_id, 200, run=retried)]

    assert logged[1:] == plain[1:]  # the block lines
    summary, plain_summary = logged[0], plain[0]
    assert summary["retries"] == 2
    assert summary["attempts"] == {
        "input_tokens": 130,
        "output_tokens": 17,
        "cost_usd": 0.75,
    }
    assert plain_summary["retries"] == 0
    assert plain_summary["attempts"]["input_tokens"] == 100
    assert summary["label"] == plain_summary["label"]  # still the first attempt
    rest = {k: v for k, v in summary.items() if k not in ("retries", "attempts")}
    plain_rest = {
        k: v for k, v in plain_summary.items() if k not in ("retries", "attempts")
    }
    assert rest == plain_rest
    assert not any(
        key in json.dumps(line)
        for line in logged
        for key in ("feedback", "unplaced_chars")
    )


def test_a_failed_request_is_one_summary_line_with_the_error():
    (line,) = request_lines("abc", 415, error="not a .docx")
    assert json.loads(line) == {
        "run_id": "abc",
        "line": "summary",
        "status": 415,
        "error": "not a .docx",
    }


# --- PII values never reach the log (Phase 2, ticket 05).


def _run_of(layout) -> Run:
    candidate, manifest, source = canary_document(layout)
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


def test_residue_of_a_failed_labelling_is_stripped_whole():
    """With no labelling nothing says which text is PII (an address, a date of
    birth, a referee), and the residue is the whole document: only its shape
    is logged (found by the canary test, ticket 10)."""
    run = Run(
        run_id="r",
        label_failed=True,
        residue=[
            Residue(
                span=Span(block_id="body:0", start=0, end=14, text="22 Larkspur Cl"),
                separator=False,
            ),
        ],
    )
    out = "".join(request_lines("r", 200, run=run))
    assert "Larkspur" not in out
    (block,) = [json.loads(line) for line in request_lines("r", 200, run=run)][1:]
    assert block["residue"][0]["span"]["length"] == 14
    assert block["residue"][0]["span"]["class"] == "99_aaaaaaaa_aa"


def test_an_error_field_is_stripped_of_pii_shaped_text():
    (line,) = request_lines(
        "abc", 500, error=f"ValueError: bad {CANARY_EMAIL} and {CANARY_PHONE}"
    )
    assert "example.invalid" not in line
    assert "7391" not in line
    assert json.loads(line)["error"].startswith("ValueError: bad ")
