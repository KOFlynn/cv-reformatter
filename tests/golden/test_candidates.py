import pytest

from cvr.golden import CANDIDATES_DIR, Tag, load_candidates

CANDIDATES = load_candidates(CANDIDATES_DIR)
BY_ID = {candidate.id: candidate for candidate in CANDIDATES}

# The spec's allocation table, verbatim: id -> tags. Order within a row is
# not meaningful, so rows compare as sets.
ALLOCATION = {
    "c01": {"punctuation-in-name"},
    "c02": {"no-profile", "empty-sections", "typo"},
    "c03": {"year-only-date", "repeat-employer"},
    "c04": {"literal-date", "non-ie-locale"},
    "c05": {"current-role", "concurrent-roles", "undated-entry"},
    "c06": {"unusual-sections", "duplicate-skill", "typo"},
    "c07": {"non-ie-locale", "inline-skills"},
    "c08": {"pii-in-bullet"},
    "c09": {"unplaceable"},
    "c10": {"non-ie-locale", "year-only-date", "date-in-body-text"},
    "c11": {"unplaceable", "has-referees"},
    "c12": {"has-personal-details", "typo"},
}


def test_candidates_directory_loads_c01():
    assert "c01" in BY_ID


def test_c01_has_every_section_and_contact_detail_the_ticket_asks_for():
    c01 = BY_ID["c01"]
    content, pii = c01.content, c01.pii
    assert (
        content.profile
        and content.skills
        and content.certifications
        and content.additional
    )
    assert len(content.education) >= 2
    assert len(content.experience) >= 3
    assert all(entry.bullets for entry in content.experience)
    assert pii.phone and pii.email and pii.address and len(pii.urls) == 1
    assert c01.unplaceable == []
    assert c01.tags == [Tag.PUNCTUATION_IN_NAME]


def test_the_twelve_candidates_are_exactly_the_allocation_table():
    assert sorted(BY_ID) == sorted(ALLOCATION)


@pytest.mark.parametrize("candidate_id", sorted(ALLOCATION))
def test_each_candidate_carries_exactly_its_allocated_tags(candidate_id):
    candidate = BY_ID.get(candidate_id)
    assert candidate is not None, f"{candidate_id} is not committed"
    assert {tag.value for tag in candidate.tags} == ALLOCATION[candidate_id]
    assert len(candidate.tags) == len(set(candidate.tags))


@pytest.mark.parametrize("candidate", CANDIDATES, ids=lambda c: c.id)
def test_every_candidate_has_phone_email_address_lines_and_a_url(candidate):
    pii = candidate.pii
    assert pii.phone and pii.email and pii.address and pii.urls


@pytest.mark.parametrize("candidate", CANDIDATES, ids=lambda c: c.id)
def test_every_candidate_has_a_name_skills_education_and_dated_experience(candidate):
    content = candidate.content
    assert content.name and content.skills and content.education and content.experience
    # The ordering metric trusts Candidate order, so at least one entry must be
    # dated for that order to mean anything.
    assert any(entry.start or entry.end for entry in content.experience)


# The misspellings behind every `typo` tag, pinned so that nobody helpfully
# normalises them out of the fixture: a StrictModel cannot carry a comment.
TYPOS = {
    "c02": ["Maintianed", "recieved"],
    "c06": ["comunication", "liased"],
    "c12": ["responsibile"],
}


def _strings(candidate) -> list[str]:
    content = candidate.content
    strings = [*content.profile, *content.certifications, *content.additional]
    for entry in content.experience:
        strings += entry.bullets
    for entry in content.education:
        strings += entry.details
    return strings


def test_typo_candidates_are_exactly_the_ones_with_pinned_misspellings():
    assert sorted(TYPOS) == sorted(c.id for c in CANDIDATES if Tag.TYPO in c.tags)


@pytest.mark.parametrize("candidate_id", sorted(TYPOS))
def test_each_pinned_misspelling_survives_in_the_fixture(candidate_id):
    strings = _strings(BY_ID[candidate_id])
    for typo in TYPOS[candidate_id]:
        assert any(typo in text for text in strings), typo
