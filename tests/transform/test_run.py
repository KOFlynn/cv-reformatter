"""``Run``: defined once, assembled by ``transform``, JSON-round-trippable."""

from transform_support import unit

from cvr.models import Normalisation, Removal, RemovalRule, Span, VerifiedContent
from cvr.transform import LedgerLine, Run, transform


def _hand_made_run() -> Run:
    """A ``Run`` built with no labeller, no verifier and no clock: every
    piece is handed in explicitly."""
    content = VerifiedContent(name=unit("Jane Doe"))
    phone_span = Span(block_id="body:1", start=0, end=11, text="087 1234567")
    _, run = transform(
        content,
        run_id="run-0001",
        ledger={
            "body:0": [LedgerLine(start=0, end=8, claimant="name", kind="content")],
            "body:1": [
                LedgerLine(start=0, end=11, claimant="RM_PHONE", kind="removal")
            ],
        },
        removals=[Removal(rule=RemovalRule.PHONE, subject=phone_span)],
        normalisations=[
            Normalisation(
                rule="NORM_INVISIBLE", block_id="body:0", characters=["\u200b"]
            )
        ],
        residue=[Span(block_id="body:2", start=0, end=3, text=" & ")],
        unplaced=[],
        label_failed=False,
        labeller_config={"provider": "anthropic", "model": "claude-opus-5"},
        prompt_label="v1",
        prompt_hash="abc123",
        schema_label="v1",
        schema_hash="def456",
        tokens={"prompt": 100, "completion": 20},
        cost=0.01,
    )
    return run


def test_run_serialises_to_json_and_back_unchanged() -> None:
    run = _hand_made_run()
    restored = Run.model_validate_json(run.model_dump_json())
    assert restored == run


def test_run_carries_every_field_the_ticket_names() -> None:
    run = _hand_made_run()
    assert run.run_id == "run-0001"
    assert run.labeller_config == {"provider": "anthropic", "model": "claude-opus-5"}
    assert run.prompt_label == "v1"
    assert run.prompt_hash == "abc123"
    assert run.schema_label == "v1"
    assert run.schema_hash == "def456"
    assert run.tokens == {"prompt": 100, "completion": 20}
    assert run.cost == 0.01
    assert "body:0" in run.ledger and "body:1" in run.ledger
    assert len(run.removals) == 1
    assert len(run.normalisations) == 1
    assert run.date_map == {}
    assert run.split_map == {}
    assert len(run.residue) == 1
    assert run.unplaced == []
    assert run.label_failed is False


def test_run_defaults_need_no_labeller_metadata() -> None:
    content = VerifiedContent()
    _, run = transform(content, run_id="run-0002")
    restored = Run.model_validate_json(run.model_dump_json())
    assert restored == run
    assert run.labeller_config == {}
    assert run.prompt_label is None
    assert run.tokens is None
