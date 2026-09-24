"""The renderer round-trip: content in, document out, adapter back, leaves
equal and in order. Proves the render/adapt pair; a composite line assembled
in the wrong order is caught here and nowhere else the eval gate can see
(ADR-0007 amendment).
"""

import pytest
from render_support import to_transformed_content, unplaced_spans

from cvr.eval import adapt
from cvr.golden import CANDIDATES_DIR, load_candidate
from cvr.render import render

CANDIDATE_FILES = sorted(CANDIDATES_DIR.glob("*.json"))
assert CANDIDATE_FILES, f"no Candidate files in {CANDIDATES_DIR}"
candidates = pytest.mark.parametrize("path", CANDIDATE_FILES, ids=lambda p: p.stem)


@candidates
def test_every_candidates_content_round_trips(path):
    candidate = load_candidate(path)
    content = to_transformed_content(candidate.content)
    adapted = adapt(render(content, []))
    assert adapted.content == content
    assert adapted.appendix == []


def test_composite_lines_split_back_into_employer_location_and_dates():
    candidate = load_candidate(CANDIDATES_DIR / "c01.json")
    content = to_transformed_content(candidate.content)
    adapted = adapt(render(content, []))
    expected = candidate.content.experience[0]
    actual = adapted.content.experience[0]
    assert actual.employer == expected.employer
    assert actual.location == expected.location
    assert actual.start == expected.start.expected
    assert actual.end == expected.end.expected


def test_unplaced_text_round_trips_and_raises_the_banner():
    candidate = load_candidate(CANDIDATES_DIR / "c01.json")
    content = to_transformed_content(candidate.content)
    fragments = ["Available from 1 September", "Full clean driving licence"]
    adapted = adapt(render(content, unplaced_spans(*fragments)))
    assert adapted.appendix == fragments
    assert adapted.content == content


def test_no_unplaced_text_means_an_empty_appendix():
    candidate = load_candidate(CANDIDATES_DIR / "c05.json")
    content = to_transformed_content(candidate.content)
    adapted = adapt(render(content, []))
    assert adapted.appendix == []
