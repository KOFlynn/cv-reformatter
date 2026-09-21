"""The verifier's output tree: ``CVContent`` with a ``Unit`` of Spans in
place of every string."""

import pytest
from pydantic import ValidationError

from cvr.models import (
    CVContent,
    Span,
    Unit,
    VerifiedContent,
    VerifiedEducation,
    VerifiedExperience,
)


def _span(start: int, end: int, block_id: str = "body:1") -> Span:
    return Span(block_id=block_id, start=start, end=end, text="x" * (end - start))


def test_unit_is_one_or_more_spans_of_one_block_ascending():
    unit = Unit(spans=[_span(0, 5), _span(10, 15)])
    assert unit.block_id == "body:1"
    assert len(unit.spans) == 2


def test_unit_must_hold_at_least_one_span():
    with pytest.raises(ValidationError):
        Unit(spans=[])


def test_unit_spans_must_share_a_block():
    with pytest.raises(ValidationError, match="block"):
        Unit(spans=[_span(0, 5), _span(10, 15, block_id="body:2")])


def test_unit_spans_must_ascend_without_overlap():
    with pytest.raises(ValidationError, match="ascending"):
        Unit(spans=[_span(10, 15), _span(0, 5)])
    with pytest.raises(ValidationError, match="ascending"):
        Unit(spans=[_span(0, 5), _span(4, 8)])
    # Touching spans are two adjacent claims, not an overlap.
    Unit(spans=[_span(0, 5), _span(5, 8)])


def test_verified_content_mirrors_cv_content():
    assert set(VerifiedContent.model_fields) == set(CVContent.model_fields)
    assert set(VerifiedExperience.model_fields) == {
        "title",
        "employer",
        "location",
        "dates",
        "bullets",
    }
    assert set(VerifiedEducation.model_fields) == {
        "institution",
        "qualification",
        "dates",
        "details",
    }


def test_verified_content_is_empty_by_default():
    # The labelling-failure tree: nothing placed, no field required.
    content = VerifiedContent()
    assert content.name is None
    assert content.skills == [] and content.experience == []
