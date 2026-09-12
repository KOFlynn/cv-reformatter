import re

import pytest

from cvr.golden import CANDIDATES_DIR, Candidate, Tag, load_candidate, load_candidates
from cvr.models import CVContent

# Parametrised over files rather than loaded Candidates so that one malformed
# file fails its own cases, not the collection of the whole module.
CANDIDATE_FILES = sorted(CANDIDATES_DIR.glob("*.json"))
EXPECTED_DATE = re.compile(r"^(0[1-9]|1[0-2])/\d{4}$|^\d{4}$|^Present$")


def _dates(content: CVContent):
    for entry in [*content.experience, *content.education]:
        yield from (date for date in (entry.start, entry.end) if date is not None)


@pytest.mark.parametrize("tag", list(Tag))
def test_every_tag_has_a_one_line_description(tag):
    assert tag.description and "\n" not in tag.description


@pytest.mark.parametrize("path", CANDIDATE_FILES, ids=lambda p: p.stem)
def test_every_carried_tag_holds(path):
    candidate = load_candidate(path)
    failing = [tag for tag in candidate.tags if not tag.holds(candidate)]
    assert failing == []


@pytest.mark.parametrize("tag", list(Tag))
def test_every_tag_is_carried_by_at_least_one_candidate(tag):
    assert any(tag in candidate.tags for candidate in load_candidates(CANDIDATES_DIR))


@pytest.mark.parametrize("path", CANDIDATE_FILES, ids=lambda p: p.stem)
def test_every_expected_date_is_normalised_or_the_literal(path):
    for date in _dates(load_candidate(path).content):
        assert EXPECTED_DATE.match(date.expected) or date.expected == date.literal, date


def _candidate(name: str) -> Candidate:
    return Candidate(id="cx", content=CVContent(name=name), pii={})


@pytest.mark.parametrize(
    "name", ["Sinéad Byrne", "Tom O'Reilly", "Tom O’Reilly", "Anna Smith-Jones"]
)
def test_punctuation_in_name_holds_for_fada_apostrophe_and_hyphen(name):
    assert Tag.PUNCTUATION_IN_NAME.holds(_candidate(name))


def test_punctuation_in_name_does_not_hold_for_a_plain_name():
    assert not Tag.PUNCTUATION_IN_NAME.holds(_candidate("Tom Byrne"))
    assert not Tag.PUNCTUATION_IN_NAME.declared
