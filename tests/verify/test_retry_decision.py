"""The retry rules: the decision, the progress measure, the feedback and N."""

import pytest
from support import block as _block
from support import experience as _experience
from support import labelling as _labelling
from support import ref as _ref

from cvr.models import LabellingFailure, RemovalReference
from cvr.verify import verify
from cvr.verify.retry import (
    DEFAULT_RETRY_MAX,
    ENV_RETRY_MAX,
    build_feedback,
    decide_retry,
    retry_max,
    unplaced_chars,
)

BLOCKS = [
    _block("body:0", "Jane Doe"),
    _block("body:1", "Sampled rivers"),
    _block("body:2", "Wrote reports"),
    _block("body:3", " - "),
]


def _first(**fields):
    return verify(BLOCKS, _labelling(**fields))


def _all_placed():
    return _first(
        name=_ref("body:0", "Jane Doe"),
        skills=[_ref("body:1", "Sampled rivers"), _ref("body:2", "Wrote reports")],
    )


def _some_unplaced():
    return _first(name=_ref("body:0", "Jane Doe"))  # 13 + 12 non-separator chars


# --- unplaced_chars


def test_unplaced_chars_counts_non_separator_characters_of_unplaced_residue():
    assert unplaced_chars(_some_unplaced()) == 25  # 13 + 12, no spaces


def test_a_mixed_run_counts_only_its_non_separator_characters():
    verified = verify([_block("body:0", "ab - cd")], _labelling())
    assert unplaced_chars(verified) == 4


def test_separator_only_residue_counts_for_nothing_and_never_triggers():
    verified = _first(
        name=_ref("body:0", "Jane Doe"),
        skills=[_ref("body:1", "Sampled rivers"), _ref("body:2", "Wrote reports")],
    )
    assert [r.separator for r in verified.residue] == [True]
    assert unplaced_chars(verified) == 0
    decision = decide_retry(verified, None, 1, 2)
    assert (decision.retry, decision.reason) == (False, "nothing_unplaced")


# --- the decision


def test_nothing_unplaced_stops():
    d = decide_retry(_all_placed(), None, 1, 2)
    assert (d.retry, d.reason) == (False, "nothing_unplaced")


def test_unplaced_text_on_the_first_attempt_retries():
    d = decide_retry(_some_unplaced(), None, 1, 2)
    assert (d.retry, d.reason) == (True, "unplaced_text")


def test_progress_retries_again_while_attempts_are_left():
    verified = _first(
        name=_ref("body:0", "Jane Doe"), skills=[_ref("body:1", "Sampled rivers")]
    )
    assert unplaced_chars(verified) == 12
    d = decide_retry(verified, 25, 2, 3)
    assert (d.retry, d.reason) == (True, "unplaced_text")


@pytest.mark.parametrize("previous", [25, 20])
def test_no_progress_stops(previous):
    d = decide_retry(_some_unplaced(), previous, 2, 3)
    assert (d.retry, d.reason) == (False, "no_progress")


def test_n_reached_stops_even_with_progress():
    d = decide_retry(_some_unplaced(), 99, 3, 2)
    assert (d.retry, d.reason) == (False, "attempts_exhausted")


def test_the_last_allowed_retry_is_still_made():
    assert decide_retry(_some_unplaced(), 99, 2, 2).retry is True


def test_n_zero_never_retries():
    d = decide_retry(_some_unplaced(), None, 1, 0)
    assert (d.retry, d.reason) == (False, "attempts_exhausted")


def test_a_retry_that_was_a_labelling_failure_stops():
    failed = verify(BLOCKS, LabellingFailure(reason="malformed"))
    d = decide_retry(failed, 25, 2, 2, "failed")
    assert (d.retry, d.reason) == (False, "retry_failed")


def test_a_retry_that_met_an_outage_stops():
    d = decide_retry(None, 25, 2, 2, "outage")
    assert (d.retry, d.reason) == (False, "outage")


def test_a_first_attempt_that_was_a_labelling_failure_is_retried():
    failed = verify(BLOCKS, LabellingFailure(reason="malformed"))
    d = decide_retry(failed, None, 1, 2, "failed")
    assert (d.retry, d.reason) == (True, "first_attempt_failed")


def test_a_failed_first_attempt_is_not_retried_when_n_is_zero():
    failed = verify(BLOCKS, LabellingFailure(reason="malformed"))
    assert decide_retry(failed, None, 1, 0, "failed").retry is False


def test_an_ok_attempt_without_a_result_is_a_misuse():
    with pytest.raises(ValueError):
        decide_retry(None, None, 1, 2)


def test_progress_after_a_failed_first_attempt_is_measured_against_everything():
    failed = verify(BLOCKS, LabellingFailure(reason="malformed"))
    before = unplaced_chars(failed)
    assert before == 7 + 13 + 12
    assert decide_retry(_some_unplaced(), before, 2, 2).retry is True


# --- feedback


def test_feedback_carries_the_unplaced_runs_by_block_and_offsets():
    fb = build_feedback(_some_unplaced())
    assert fb.unusable is False
    assert [(u.block_id, u.start, u.end) for u in fb.unplaced] == [
        ("body:1", 0, 14),
        ("body:2", 0, 13),
    ]
    # the text is recovered from the blocks by offset
    by_id = {b.id: b.text for b in BLOCKS}
    assert [by_id[u.block_id][u.start : u.end] for u in fb.unplaced] == [
        "Sampled rivers",
        "Wrote reports",
    ]


def test_feedback_has_no_text_in_its_stored_form():
    fb = build_feedback(
        _first(
            name=_ref("body:0", "Jane Doe"),
            skills=[_ref("body:1", "Sampled rivers"), _ref("body:2", "Nonexistent")],
        )
    )
    assert fb.unlocatable
    dumped = fb.model_dump_json()
    for text in ("Sampled", "Wrote", "Nonexistent", "Jane"):
        assert text not in dumped


def test_an_unlocatable_rejection_in_a_block_with_unplaced_text_is_a_hint():
    verified = _first(
        name=_ref("body:0", "Jane Doe"),
        skills=[_ref("body:2", "Wrote a report")],  # not in the block
    )
    assert [(r.path, r.reason) for r in verified.rejections] == [
        ("skills[0]", "unlocatable")
    ]
    fb = build_feedback(verified)
    assert [(h.path, h.block_id) for h in fb.unlocatable] == [("skills[0]", "body:2")]


def test_an_unlocatable_rejection_in_a_fully_placed_block_is_not_a_hint():
    verified = _first(
        name=_ref("body:0", "Jane Doe"),
        skills=[
            _ref("body:1", "Sampled rivers"),
            _ref("body:2", "Wrote reports"),
            _ref("body:0", "Janet"),  # unlocatable, but body:0 is placed
        ],
    )
    assert [r.reason for r in verified.rejections] == ["unlocatable"]
    assert verified.unplaced == []
    assert build_feedback(verified).unlocatable == []


def test_conflict_and_removed_are_never_feedback():
    blocks = [
        _block("body:0", "Sampled rivers 087 1234567"),
        _block("body:1", "left over"),
    ]
    verified = verify(
        blocks,
        _labelling(
            skills=[
                _ref("body:0", "Sampled rivers"),
                _ref("body:0", "Sampled rivers"),  # takes no second occurrence
                _ref("body:0", "087 1234567"),  # removed by the phone backstop
            ],
        ),
    )
    assert {r.reason for r in verified.rejections} >= {"conflict", "removed"}
    assert build_feedback(verified).unlocatable == []


def test_an_unlocatable_removal_is_not_a_hint():
    blocks = [_block("body:0", "Jane Doe"), _block("body:1", "left over")]
    verified = verify(
        blocks,
        _labelling(
            name=_ref("body:0", "Jane Doe"),
            removals=[
                RemovalReference(block_id="body:1", rule="RM_PERSONAL", quote="no")
            ],
        ),
    )
    assert [r.path for r in verified.rejections] == ["removals[0]"]
    assert build_feedback(verified).unlocatable == []


def test_a_labelling_failure_is_unusable_and_all_its_text_is_unplaced():
    fb = build_feedback(verify(BLOCKS, LabellingFailure(reason="malformed")))
    assert fb.unusable is True
    assert [u.block_id for u in fb.unplaced] == ["body:0", "body:1", "body:2"]
    assert fb.unlocatable == []


def test_a_hint_names_an_experience_path():
    blocks = [_block("body:0", "Hydrologist"), _block("body:1", "Did things")]
    verified = verify(
        blocks,
        _labelling(
            experience=[
                _experience(
                    title=_ref("body:0", "Hydrologist"),
                    bullets=[_ref("body:1", "Did thing x")],
                )
            ]
        ),
    )
    fb = build_feedback(verified)
    assert [(h.path, h.block_id) for h in fb.unlocatable] == [
        ("experience[0].bullets[0]", "body:1")
    ]


# --- N


def test_n_defaults_to_two():
    assert DEFAULT_RETRY_MAX == 2
    assert retry_max({}) == 2
    assert retry_max({ENV_RETRY_MAX: ""}) == 2


def test_n_is_read_from_cvr_retry_max():
    assert ENV_RETRY_MAX == "CVR_RETRY_MAX"
    assert retry_max({ENV_RETRY_MAX: "3"}) == 3
    assert retry_max({ENV_RETRY_MAX: "0"}) == 0


@pytest.mark.parametrize("bad", ["-1", "two", "1.5", "٣"])
def test_a_bad_n_raises_naming_the_variable(bad):
    with pytest.raises(ValueError, match=ENV_RETRY_MAX):
        retry_max({ENV_RETRY_MAX: bad})


def test_n_comes_from_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv(ENV_RETRY_MAX, "5")
    assert retry_max() == 5
