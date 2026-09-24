"""``Run``: defined once in ``models``, each node filling its own section,
JSON-round-trippable, and buildable by hand with no labeller."""

from cvr.models import (
    LabelRun,
    LedgerEntry,
    LedgerKind,
    Normalisation,
    Removal,
    RemovalRule,
    Residue,
    Run,
    Span,
    Unit,
    VerifiedContent,
    VerifiedExperience,
)
from cvr.transform import transform_content


def _span(block_id: str, start: int, text: str) -> Span:
    return Span(block_id=block_id, start=start, end=start + len(text), text=text)


def _hand_made_run() -> Run:
    """A ``Run`` from a hand-made ``VerifiedContent``: transform's section
    comes from the real ``transform_content``, every other section is handed
    in explicitly."""
    dates = _span("body:3", 0, "Jan 2020 - Present")
    content = VerifiedContent(
        name=Unit(spans=[_span("body:0", 0, "Jane Doe")]),
        experience=[VerifiedExperience(dates=Unit(spans=[dates]))],
    )
    transformed = transform_content(content)
    phone = _span("body:1", 0, "087 1234567")
    return Run(
        run_id="run-0001",
        label=LabelRun(
            config={"provider": "anthropic", "model": "claude-opus-5-5"},
            prompt_version="1.0.0",
            prompt_hash="abc123",
            schema_version="1.0.0",
            schema_hash="def456",
            content_hash="0123abcd",
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.01,
        ),
        normalisations=[
            Normalisation(
                rule="NORM_INVISIBLE", block_id="body:0", characters=["\u200b"]
            )
        ],
        removals=[Removal(rule=RemovalRule.PHONE, subject=phone)],
        ledgers={
            "body:0": [
                LedgerEntry(start=0, end=8, claimant="name", kind=LedgerKind.CONTENT)
            ],
            "body:1": [
                LedgerEntry(
                    start=0, end=11, claimant="RM_PHONE", kind=LedgerKind.REMOVAL
                )
            ],
        },
        residue=[
            Residue(span=_span("body:2", 0, ", "), separator=True),
            Residue(span=_span("body:2", 2, "Tipperary"), separator=False),
        ],
        date_map=transformed.date_map,
        split_map=transformed.split_map,
    )


def test_run_serialises_to_json_and_back_unchanged() -> None:
    run = _hand_made_run()
    assert Run.model_validate_json(run.model_dump_json()) == run


def test_run_carries_every_section() -> None:
    run = _hand_made_run()
    assert run.label is not None and run.label.prompt_hash == "abc123"
    assert set(run.ledgers) == {"body:0", "body:1"}
    assert len(run.removals) == 1
    assert len(run.normalisations) == 1
    assert set(run.date_map) == {"01/2020", "Present"}
    assert run.split_map == {}
    assert run.label_failed is False


def test_unplaced_is_the_residue_that_is_not_separator() -> None:
    run = _hand_made_run()
    assert [span.text for span in run.unplaced] == ["Tipperary"]


def test_run_needs_no_labeller() -> None:
    run = Run(run_id="run-0002")
    assert Run.model_validate_json(run.model_dump_json()) == run
    assert run.label is None
    assert run.unplaced == []
