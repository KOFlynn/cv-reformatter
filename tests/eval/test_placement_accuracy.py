"""placement_accuracy: hand-made CVContent pairs in, a PlacementReport out."""

from cvr.eval import AlignedBy, Alignment, FieldType, Section, Tally, placement_accuracy
from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry


def date(year: int, month: int) -> DateValue:
    return DateValue(year=year, month=month, expected=f"{month:02d}/{year}")


SENIOR = ExperienceEntry(
    title="Senior Engineer",
    employer="Liffey Analytics",
    location="Dublin",
    start=date(2022, 3),
    end=date(2026, 7),
    bullets=["Led the migration.", "Mentored two graduates."],
)
JUNIOR = ExperienceEntry(
    title="Engineer",
    employer="Shamrock Data",
    location="Cork",
    start=date(2018, 10),
    end=date(2022, 2),
    bullets=["Built ETL jobs.", "Wrote the runbook."],
)
MSC = EducationEntry(
    institution="University College Cork",
    qualification="MSc in Data Science",
    start=date(2015, 9),
    end=date(2016, 8),
    details=["Dissertation on bus arrival times"],
)
EXPECTED = CVContent(
    name="Sinéad O'Sampla",
    profile=["Software engineer with eight years of experience."],
    skills=["Python", "SQL", "Docker"],
    education=[MSC],
    experience=[SENIOR, JUNIOR],
    certifications=["CKAD"],
    additional=["Languages: English, Irish"],
)
# name 1, profile 1, skills 3, education 5 (institution, qualification, two
# dates, one detail), experience 2 x 7 (title, employer, location, two dates,
# two bullets), certifications 1, additional 1.
TOTAL_LEAVES = 1 + 1 + 3 + 5 + 14 + 1 + 1


def test_identical_content_scores_one_everywhere_and_aligns_every_entry_on_key():
    report = placement_accuracy(EXPECTED, EXPECTED)
    assert report.overall.precision == 1.0
    assert report.overall.recall == 1.0
    assert report.alignments == (
        Alignment(Section.EXPERIENCE, expected=0, actual=0, aligned_by=AlignedBy.KEY),
        Alignment(Section.EXPERIENCE, expected=1, actual=1, aligned_by=AlignedBy.KEY),
        Alignment(Section.EDUCATION, expected=0, actual=0, aligned_by=AlignedBy.KEY),
    )
    assert report.unaligned_entries == {Section.EXPERIENCE: 0, Section.EDUCATION: 0}


def with_experience(*entries: ExperienceEntry) -> CVContent:
    return EXPECTED.model_copy(update={"experience": list(entries)})


def test_one_wrong_employer_aligns_on_the_fallback_pass_and_costs_one_leaf():
    actual = with_experience(
        SENIOR.model_copy(update={"employer": "Liffy Analytics"}), JUNIOR
    )
    report = placement_accuracy(actual, EXPECTED)
    assert report.alignments[0] == Alignment(
        Section.EXPERIENCE, expected=0, actual=0, aligned_by=AlignedBy.FALLBACK
    )
    assert report.by_field[FieldType.EMPLOYER] == Tally(hits=1, actual=2, expected=2)
    assert report.overall == Tally(
        hits=TOTAL_LEAVES - 1, actual=TOTAL_LEAVES, expected=TOTAL_LEAVES
    )
    assert report.unaligned_entries == {Section.EXPERIENCE: 0, Section.EDUCATION: 0}


def test_swapped_title_and_employer_aligns_on_the_fallback_pass_and_costs_two_leaves():
    # Every leaf is still there, so the overlap is total; but title and
    # employer are each in the wrong field, and a wrong field is a miss.
    swapped = SENIOR.model_copy(
        update={"title": SENIOR.employer, "employer": SENIOR.title}
    )
    report = placement_accuracy(with_experience(swapped, JUNIOR), EXPECTED)
    assert report.alignments[0].aligned_by is AlignedBy.FALLBACK
    assert report.by_field[FieldType.TITLE] == Tally(hits=1, actual=2, expected=2)
    assert report.by_field[FieldType.EMPLOYER] == Tally(hits=1, actual=2, expected=2)
    assert report.overall == Tally(
        hits=TOTAL_LEAVES - 2, actual=TOTAL_LEAVES, expected=TOTAL_LEAVES
    )


def test_a_lost_entry_is_unmatched_and_every_one_of_its_leaves_misses_recall_only():
    report = placement_accuracy(with_experience(SENIOR), EXPECTED)
    assert report.alignments[1] == Alignment(
        Section.EXPERIENCE, expected=1, actual=None, aligned_by=AlignedBy.UNMATCHED
    )
    assert report.unaligned_entries == {Section.EXPERIENCE: 1, Section.EDUCATION: 0}
    # JUNIOR's seven leaves are wanted and not found; nothing placed is wrong.
    assert report.overall == Tally(
        hits=TOTAL_LEAVES - 7, actual=TOTAL_LEAVES - 7, expected=TOTAL_LEAVES
    )
    assert report.overall.precision == 1.0
    assert report.overall.recall < 1.0


def test_an_invented_entry_is_unmatched_and_every_one_of_its_leaves_misses_precision_only():
    invented = ExperienceEntry(
        title="Intern", employer="Nowhere Ltd", bullets=["Made tea."]
    )
    report = placement_accuracy(with_experience(SENIOR, JUNIOR, invented), EXPECTED)
    assert report.alignments[2] == Alignment(
        Section.EXPERIENCE, expected=None, actual=2, aligned_by=AlignedBy.UNMATCHED
    )
    assert report.unaligned_entries == {Section.EXPERIENCE: 1, Section.EDUCATION: 0}
    assert report.overall == Tally(
        hits=TOTAL_LEAVES, actual=TOTAL_LEAVES + 3, expected=TOTAL_LEAVES
    )
    assert report.overall.recall == 1.0
    assert report.overall.precision < 1.0


def test_an_entry_sharing_less_than_half_its_leaves_is_not_aligned_on_the_fallback_pass():
    # Title and employer only, one of them wrong: one shared leaf of three.
    expected = with_experience(
        ExperienceEntry(title="Engineer", employer="Shamrock Data")
    )
    actual = with_experience(
        ExperienceEntry(title="Engineer", employer="Shamrock Data Systems")
    )
    report = placement_accuracy(actual, expected)
    assert [a.aligned_by for a in report.alignments[:2]] == [AlignedBy.UNMATCHED] * 2
    assert report.unaligned_entries[Section.EXPERIENCE] == 2
    assert report.by_field[FieldType.TITLE] == Tally(hits=0, actual=1, expected=1)


def test_an_entry_sharing_exactly_half_its_leaves_is_aligned_on_the_fallback_pass():
    # Title, employer and location, one of them wrong: two shared leaves over
    # a union of four is exactly the cutoff, and the cutoff is inclusive.
    expected = with_experience(
        ExperienceEntry(title="Engineer", employer="Shamrock Data", location="Cork")
    )
    actual = with_experience(
        ExperienceEntry(
            title="Engineer", employer="Shamrock Data Systems", location="Cork"
        )
    )
    report = placement_accuracy(actual, expected)
    assert report.alignments[0].aligned_by is AlignedBy.FALLBACK


def test_a_promotion_at_one_employer_aligns_both_roles_on_key():
    # Same employer twice; the structured start date tells the two apart, so
    # the key pass pairs each role with its own, even when the actual order
    # is reversed.
    promoted = SENIOR.model_copy(update={"employer": JUNIOR.employer})
    expected = with_experience(promoted, JUNIOR)
    report = placement_accuracy(with_experience(JUNIOR, promoted), expected)
    assert report.alignments[:2] == (
        Alignment(Section.EXPERIENCE, expected=0, actual=1, aligned_by=AlignedBy.KEY),
        Alignment(Section.EXPERIENCE, expected=1, actual=0, aligned_by=AlignedBy.KEY),
    )
    assert report.overall.precision == report.overall.recall == 1.0


def test_a_duplicated_skill_is_counted_with_multiplicity():
    expected = EXPECTED.model_copy(update={"skills": ["Python", "SQL", "Python"]})
    once = EXPECTED.model_copy(update={"skills": ["Python", "SQL"]})
    assert placement_accuracy(once, expected).by_field[FieldType.SKILL] == Tally(
        hits=2, actual=2, expected=3
    )
    thrice = EXPECTED.model_copy(
        update={"skills": ["Python", "SQL", "Python", "Python"]}
    )
    assert placement_accuracy(thrice, expected).by_field[FieldType.SKILL] == Tally(
        hits=3, actual=4, expected=3
    )


def test_structural_and_tunable_field_types_are_reported_apart():
    wrong_bullet = SENIOR.model_copy(
        update={"bullets": ["Led the migration.", "Made tea."]}
    )
    report = placement_accuracy(with_experience(wrong_bullet, JUNIOR), EXPECTED)
    assert report.structural.precision == report.structural.recall == 1.0
    assert report.tunable == Tally(hits=10, actual=11, expected=11)
    assert {f for f in FieldType if f.structural} == {
        FieldType.NAME,
        FieldType.TITLE,
        FieldType.EMPLOYER,
        FieldType.LOCATION,
        FieldType.DATE,
        FieldType.INSTITUTION,
        FieldType.QUALIFICATION,
    }
    assert set(report.by_field) == set(FieldType)


def test_a_wrong_date_is_a_structural_miss_on_the_date_field():
    late = SENIOR.model_copy(update={"end": date(2026, 8)})
    report = placement_accuracy(with_experience(late, JUNIOR), EXPECTED)
    assert report.alignments[0].aligned_by is AlignedBy.KEY
    assert report.by_field[FieldType.DATE] == Tally(hits=5, actual=6, expected=6)
    assert report.structural.recall < 1.0


def test_a_location_present_on_one_side_only_misses_on_that_side_only():
    report = placement_accuracy(
        with_experience(SENIOR.model_copy(update={"location": None}), JUNIOR), EXPECTED
    )
    assert report.by_field[FieldType.LOCATION] == Tally(hits=1, actual=1, expected=2)
    report = placement_accuracy(
        EXPECTED, with_experience(SENIOR.model_copy(update={"location": None}), JUNIOR)
    )
    assert report.by_field[FieldType.LOCATION] == Tally(hits=1, actual=2, expected=1)


def test_leaves_are_compared_canonicalised():
    curly = EXPECTED.model_copy(
        update={"name": "Sinéad O’Sampla", "skills": ["Python", "SQL", "Docker "]}
    )
    report = placement_accuracy(curly, EXPECTED)
    assert report.overall.precision == report.overall.recall == 1.0


def test_a_wrong_qualification_aligns_education_on_the_fallback_pass():
    phd = MSC.model_copy(update={"qualification": "PhD in Data Science"})
    report = placement_accuracy(
        EXPECTED.model_copy(update={"education": [phd]}), EXPECTED
    )
    assert report.alignments[2] == Alignment(
        Section.EDUCATION, expected=0, actual=0, aligned_by=AlignedBy.FALLBACK
    )
    assert report.by_field[FieldType.QUALIFICATION] == Tally(
        hits=0, actual=1, expected=1
    )


def test_a_name_alone_scores_one_everywhere():
    bare = CVContent(name="Anon")
    report = placement_accuracy(bare, bare)
    assert report.overall == Tally(hits=1, actual=1, expected=1)
    assert all(t.precision == t.recall == 1.0 for t in report.by_field.values())
    assert report.alignments == ()
    assert report.unaligned_entries == {Section.EXPERIENCE: 0, Section.EDUCATION: 0}
