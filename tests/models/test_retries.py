"""``Run.retries``: optional, empty by default, JSON-round-trippable, text-free;
a Run without retries serialises as it did before they existed."""

import json

from cvr.models import LabelRun, RetryRejection, RetryRun, Run
from cvr.models.feedback import Feedback, UnlocatableHint, UnplacedRun

LABEL = LabelRun(
    config={"model": "m"},
    prompt_version="1",
    prompt_hash="p",
    schema_version="1",
    schema_hash="s",
    content_hash="c",
)


def _retry() -> RetryRun:
    return RetryRun(
        label=LABEL,
        feedback=Feedback(
            unplaced=[UnplacedRun(block_id="body:1", start=0, end=5)],
            unlocatable=[UnlocatableHint(path="skills[0]", block_id="body:1")],
        ),
        rejections=[
            RetryRejection(path="skills[1]", block_id="body:1", reason="bad_path")
        ],
        unplaced_chars=3,
    )


def test_retries_default_to_empty():
    assert Run(run_id="r").retries == []


def test_a_run_without_retries_serialises_without_the_key():
    run = Run(run_id="r", label=LABEL)
    assert "retries" not in run.model_dump()
    assert "retries" not in json.loads(run.model_dump_json())


def test_a_run_saved_before_retries_existed_still_loads():
    saved = Run(run_id="r", label=LABEL).model_dump_json()
    assert Run.model_validate_json(saved).retries == []


def test_a_run_with_retries_round_trips_through_json():
    run = Run(run_id="r", label=LABEL, retries=[_retry(), _retry()])
    again = Run.model_validate_json(run.model_dump_json())
    assert again == run
    assert len(json.loads(run.model_dump_json())["retries"]) == 2


def test_a_retry_record_holds_no_text_field():
    assert set(RetryRejection.model_fields) == {"path", "block_id", "reason"}
    assert set(Feedback.model_fields) == {"unusable", "unplaced", "unlocatable"}
