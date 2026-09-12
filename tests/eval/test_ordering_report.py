"""ordering_report: hand-made CVContent pairs in, an OrderingReport out.

The expected content is already in output order (end descending with
Present first, then start descending, then source order), so the metric
only has to compare sequences; the tiebreak cases prove it never treats
equal-dated entries as interchangeable.
"""

from cvr.eval import Section, ordering_report
from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry


def date(year: int, month: int) -> DateValue:
    return DateValue(year=year, month=month, expected=f"{month:02d}/{year}")


SENIOR = ExperienceEntry(
    title="Senior Engineer",
    employer="Liffey Analytics",
    start=date(2022, 3),
    end=date(2026, 7),
    bullets=["Led the migration.", "Mentored two graduates."],
)
JUNIOR = ExperienceEntry(
    title="Engineer",
    employer="Shamrock Data",
    start=date(2018, 10),
    end=date(2022, 2),
    bullets=["Built ETL jobs.", "Wrote the runbook."],
)
GRADUATE = ExperienceEntry(
    title="Graduate",
    employer="Bandon Bay",
    start=date(2016, 9),
    end=date(2018, 9),
    bullets=["Developed internal tools."],
)
MSC = EducationEntry(institution="UCC", qualification="MSc", start=date(2015, 9))
BA = EducationEntry(institution="TCD", qualification="BA", start=date(2011, 9))
EXPECTED = CVContent(
    name="Sinéad O'Sampla", experience=[SENIOR, JUNIOR, GRADUATE], education=[MSC, BA]
)

SENIOR_KEY = ("Liffey Analytics", (2022, 3))
JUNIOR_KEY = ("Shamrock Data", (2018, 10))
GRADUATE_KEY = ("Bandon Bay", (2016, 9))


def with_experience(*entries: ExperienceEntry) -> CVContent:
    return EXPECTED.model_copy(update={"experience": list(entries)})


def test_identical_content_is_correctly_ordered_in_every_section():
    report = ordering_report(EXPECTED, EXPECTED)
    assert report.correct
    experience = report.sections[Section.EXPERIENCE]
    assert experience.correct
    assert experience.expected == (SENIOR_KEY, JUNIOR_KEY, GRADUATE_KEY)
    assert experience.actual == (SENIOR_KEY, JUNIOR_KEY, GRADUATE_KEY)
    assert experience.unmatched == 0
    assert report.sections[Section.EDUCATION].correct


def test_reversed_experience_fails_that_section_and_no_other():
    report = ordering_report(with_experience(GRADUATE, JUNIOR, SENIOR), EXPECTED)
    assert not report.correct
    experience = report.sections[Section.EXPERIENCE]
    assert not experience.correct
    assert experience.actual == (GRADUATE_KEY, JUNIOR_KEY, SENIOR_KEY)
    assert experience.unmatched == 0
    assert report.sections[Section.EDUCATION].correct


def test_a_lost_entry_is_counted_as_unmatched_and_the_rest_are_still_compared():
    # Ordering is never silently green on a broken document: the matched
    # subsequence is in order, so ``correct`` holds, and the report says in
    # the same breath that one entry never made it into the comparison.
    report = ordering_report(with_experience(SENIOR, GRADUATE), EXPECTED)
    experience = report.sections[Section.EXPERIENCE]
    assert experience.correct
    assert experience.expected == (SENIOR_KEY, GRADUATE_KEY)
    assert experience.actual == (SENIOR_KEY, GRADUATE_KEY)
    assert experience.unmatched == 1
    assert report.unmatched == {Section.EXPERIENCE: 1, Section.EDUCATION: 0}


def test_an_entry_found_with_a_wrong_key_is_placed_in_the_sequence_by_its_expected_key():
    misspelt = JUNIOR.model_copy(update={"employer": "Shamrock Dta"})
    report = ordering_report(with_experience(SENIOR, GRADUATE, misspelt), EXPECTED)
    experience = report.sections[Section.EXPERIENCE]
    assert experience.actual == (SENIOR_KEY, GRADUATE_KEY, JUNIOR_KEY)
    assert experience.unmatched == 0
    assert not experience.correct


def test_concurrent_roles_with_equal_dates_must_keep_source_order():
    # Both end Present and start the same month: the Candidate's order is
    # the tiebreak, and reversing it is an ordering error like any other.
    present = DateValue(present=True, expected="Present")
    first = ExperienceEntry(
        title="Advisor", employer="Board A", start=date(2024, 1), end=present
    )
    second = ExperienceEntry(
        title="Mentor", employer="Board B", start=date(2024, 1), end=present
    )
    expected = with_experience(first, second, JUNIOR)
    assert ordering_report(with_experience(first, second, JUNIOR), expected).correct
    assert not ordering_report(with_experience(second, first, JUNIOR), expected).correct


def test_reversed_education_fails_that_section():
    report = ordering_report(
        EXPECTED.model_copy(update={"education": [BA, MSC]}), EXPECTED
    )
    education = report.sections[Section.EDUCATION]
    assert not education.correct
    assert education.expected == (("UCC", "MSc"), ("TCD", "BA"))
    assert education.actual == (("TCD", "BA"), ("UCC", "MSc"))
    assert report.sections[Section.EXPERIENCE].correct


def test_no_entries_at_all_is_correctly_ordered():
    bare = CVContent(name="Anon")
    report = ordering_report(bare, bare)
    assert report.correct
    assert report.sections[Section.EXPERIENCE].expected == ()
    assert report.sections[Section.EXPERIENCE].unmatched == 0
