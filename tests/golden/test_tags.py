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


# --- The vocabulary


def test_tag_vocabulary_is_exactly_the_spec_list():
    assert [tag.value for tag in Tag] == [
        "no-profile",
        "typo",
        "year-only-date",
        "literal-date",
        "undated-entry",
        "current-role",
        "pii-in-bullet",
        "unplaceable",
        "has-referees",
        "has-personal-details",
        "date-in-body-text",
        "unusual-sections",
        "non-ie-locale",
        "repeat-employer",
        "concurrent-roles",
        "duplicate-skill",
        "empty-sections",
        "punctuation-in-name",
        "inline-skills",
    ]


# --- Predicates, on hand-built Candidates


def _date(**parts) -> dict:
    return parts


def _job(employer="Acme Ltd", start=None, end=None, bullets=("Did things.",)) -> dict:
    return {
        "title": "Engineer",
        "employer": employer,
        "start": start,
        "end": end,
        "bullets": list(bullets),
    }


def _course(start=None, end=None) -> dict:
    return {
        "institution": "Some College",
        "qualification": "BSc",
        "start": start,
        "end": end,
    }


def _build(*, content: dict | None = None, pii: dict | None = None, **top) -> Candidate:
    return Candidate(
        id="cx", content={"name": "Tom Byrne", **(content or {})}, pii=pii or {}, **top
    )


MMYYYY = _date(month=3, year=2021, expected="03/2021")
PRESENT = _date(present=True, expected="Present")


def test_no_profile_holds_only_when_the_profile_is_empty():
    assert Tag.NO_PROFILE.holds(_build())
    assert not Tag.NO_PROFILE.holds(_build(content={"profile": ["A line."]}))


def test_year_only_date_holds_for_a_year_with_no_month_in_either_section():
    year_only = _date(year=2014, expected="2014")
    assert Tag.YEAR_ONLY_DATE.holds(
        _build(content={"education": [_course(end=year_only)]})
    )
    assert Tag.YEAR_ONLY_DATE.holds(
        _build(content={"experience": [_job(start=year_only)]})
    )
    assert not Tag.YEAR_ONLY_DATE.holds(
        _build(content={"experience": [_job(start=MMYYYY, end=PRESENT)]})
    )


def test_literal_date_holds_only_when_a_date_carries_a_literal():
    literal = _date(year=2020, literal="Summer 2020", expected="Summer 2020")
    assert Tag.LITERAL_DATE.holds(_build(content={"experience": [_job(end=literal)]}))
    assert not Tag.LITERAL_DATE.holds(
        _build(content={"experience": [_job(end=MMYYYY)]})
    )


def test_undated_entry_holds_when_an_entry_has_neither_date():
    assert Tag.UNDATED_ENTRY.holds(_build(content={"experience": [_job()]}))
    assert Tag.UNDATED_ENTRY.holds(_build(content={"education": [_course()]}))
    assert not Tag.UNDATED_ENTRY.holds(
        _build(content={"experience": [_job(start=MMYYYY)]})
    )
    assert not Tag.UNDATED_ENTRY.holds(_build())


def test_current_role_holds_when_an_experience_entry_ends_present():
    assert Tag.CURRENT_ROLE.holds(_build(content={"experience": [_job(end=PRESENT)]}))
    assert not Tag.CURRENT_ROLE.holds(
        _build(content={"experience": [_job(end=MMYYYY)]})
    )
    # A course still running is not a current role.
    assert not Tag.CURRENT_ROLE.holds(
        _build(content={"education": [_course(end=PRESENT)]})
    )


def test_concurrent_roles_holds_when_two_experience_entries_end_present():
    both = [_job(employer="A", end=PRESENT), _job(employer="B", end=PRESENT)]
    assert Tag.CONCURRENT_ROLES.holds(_build(content={"experience": both}))
    one = [_job(employer="A", end=PRESENT), _job(employer="B", end=MMYYYY)]
    assert not Tag.CONCURRENT_ROLES.holds(_build(content={"experience": one}))


def test_repeat_employer_holds_when_two_entries_share_an_employer_after_canonicalisation():
    twice = [_job(employer="Acme Ltd", start=MMYYYY), _job(employer="Acme  Ltd")]
    assert Tag.REPEAT_EMPLOYER.holds(_build(content={"experience": twice}))
    distinct = [_job(employer="Acme Ltd"), _job(employer="Beta Ltd")]
    assert not Tag.REPEAT_EMPLOYER.holds(_build(content={"experience": distinct}))


def test_duplicate_skill_holds_when_a_skill_repeats_after_canonicalisation():
    assert Tag.DUPLICATE_SKILL.holds(
        _build(content={"skills": ["Python", "SQL", "Python"]})
    )
    assert not Tag.DUPLICATE_SKILL.holds(
        _build(content={"skills": ["Python", "python"]})
    )
    assert not Tag.DUPLICATE_SKILL.holds(_build(content={"skills": ["Python", "SQL"]}))


def test_empty_sections_holds_only_when_certifications_and_additional_are_both_empty():
    assert Tag.EMPTY_SECTIONS.holds(_build())
    assert not Tag.EMPTY_SECTIONS.holds(_build(content={"certifications": ["CKAD"]}))
    assert not Tag.EMPTY_SECTIONS.holds(
        _build(content={"additional": ["Interests: chess"]})
    )


def test_unplaceable_holds_when_the_candidate_has_fragments():
    assert Tag.UNPLACEABLE.holds(_build(unplaceable=["Page 1 of 2"]))
    assert not Tag.UNPLACEABLE.holds(_build())


def test_has_referees_holds_when_the_pii_lists_a_referee():
    assert Tag.HAS_REFEREES.holds(_build(pii={"referees": [{"name": "Pat Nobody"}]}))
    assert not Tag.HAS_REFEREES.holds(_build())


@pytest.mark.parametrize(
    "pii",
    [
        {"dob": "01/01/1990"},
        {"personal": {"nationality": "Irish"}},
        {"personal": {"marital_status": "Single"}},
    ],
)
def test_has_personal_details_holds_for_dob_nationality_or_marital_status(pii):
    assert Tag.HAS_PERSONAL_DETAILS.holds(_build(pii=pii))


def test_has_personal_details_does_not_hold_for_contact_details_alone():
    assert not Tag.HAS_PERSONAL_DETAILS.holds(
        _build(pii={"phone": "+353 87 555 0000", "email": "t@example.com"})
    )


@pytest.mark.parametrize(
    "content",
    [
        {"certifications": ["First Aid Responder (renewed March 2024)"]},
        {"experience": [_job(bullets=["Won the 2019 hackathon."])]},
        {"education": [{**_course(), "details": ["Class of 2012"]}]},
        {"additional": ["Volunteering: marshal at the 2023 marathon"]},
        {"profile": ["Engineer since 2010."]},
    ],
)
def test_date_in_body_text_holds_for_a_year_inside_any_body_string(content):
    assert Tag.DATE_IN_BODY_TEXT.holds(_build(content=content))


def test_date_in_body_text_ignores_entry_dates_and_plain_numbers():
    content = {
        "experience": [
            _job(start=MMYYYY, end=PRESENT, bullets=["Cut costs by 1500 euro."])
        ],
        "certifications": ["Cert number 20201"],
    }
    assert not Tag.DATE_IN_BODY_TEXT.holds(_build(content=content))


@pytest.mark.parametrize(
    "tag",
    [
        Tag.TYPO,
        Tag.UNUSUAL_SECTIONS,
        Tag.NON_IE_LOCALE,
        Tag.INLINE_SKILLS,
        Tag.PII_IN_BULLET,
    ],
)
def test_source_side_traps_are_author_declared(tag):
    assert tag.declared
    assert tag.holds(_build())


@pytest.mark.parametrize("tag", list(Tag))
def test_only_declared_tags_hold_on_a_bare_candidate_except_the_empty_section_ones(tag):
    # A bare Candidate has no profile and empty sections; every other computable
    # predicate must be false on it, or it is not really checking anything.
    bare = _build()
    expected = tag.declared or tag in {Tag.NO_PROFILE, Tag.EMPTY_SECTIONS}
    assert tag.holds(bare) == expected
