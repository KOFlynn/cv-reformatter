"""Feedback is ids, offsets and paths only (ticket 12's fixed interface)."""

import pytest
from pydantic import ValidationError

from cvr.models.feedback import Feedback, UnlocatableHint, UnplacedRun


def test_the_default_feedback_asks_for_nothing_and_is_usable():
    feedback = Feedback()
    assert feedback.unusable is False
    assert feedback.unplaced == []
    assert feedback.unlocatable == []


def test_feedback_round_trips_through_json():
    feedback = Feedback(
        unplaced=[UnplacedRun(block_id="body:3", start=2, end=9)],
        unlocatable=[UnlocatableHint(path="skills[1]", block_id="body:4")],
    )
    assert Feedback.model_validate_json(feedback.model_dump_json()) == feedback


def test_defaults_are_not_shared_between_instances():
    first, second = Feedback(), Feedback()
    first.unplaced.append(UnplacedRun(block_id="body:0", start=0, end=1))
    assert second.unplaced == []


def test_it_holds_no_text_field():
    assert set(UnplacedRun.model_fields) == {"block_id", "start", "end"}
    assert set(UnlocatableHint.model_fields) == {"path", "block_id"}
    with pytest.raises(ValidationError):
        UnplacedRun(block_id="body:0", start=0, end=1, text="x")


def test_an_offset_cannot_be_negative():
    with pytest.raises(ValidationError):
        UnplacedRun(block_id="body:0", start=-1, end=1)
