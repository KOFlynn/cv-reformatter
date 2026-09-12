import subprocess
import sys

import pytest
from pydantic import ValidationError

from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry


def test_models_import_without_the_golden_set_package():
    code = "import sys, cvr.models; sys.exit('cvr.golden' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_date_expected_is_required_even_when_structured_parts_are_given():
    with pytest.raises(ValidationError, match="expected"):
        DateValue(month=3, year=2021)


def test_date_carries_hand_written_expected_alongside_structured_parts():
    date = DateValue(month=3, year=2021, expected="03/2021")
    assert (date.month, date.year, date.present, date.literal) == (3, 2021, False, None)


def test_literal_date_keeps_its_text():
    date = DateValue(year=2020, literal="Summer 2020", expected="Summer 2020")
    assert date.literal == "Summer 2020"


def test_content_defaults_absent_sections_to_empty_lists():
    content = CVContent(name="Sinéad O'Sampla")
    assert (content.profile, content.skills, content.education) == ([], [], [])
    assert (content.experience, content.certifications, content.additional) == (
        [],
        [],
        [],
    )


def test_entries_hold_plain_strings_and_optional_dates():
    job = ExperienceEntry(
        title="Engineer", employer="Acme Ltd", bullets=["Built things"]
    )
    course = EducationEntry(
        institution="TCD", qualification="BSc", details=["First class"]
    )
    assert (job.location, job.start, job.end) == (None, None, None)
    assert (course.start, course.end) == (None, None)


def test_unknown_keys_are_rejected_so_fixture_typos_fail_fast():
    with pytest.raises(ValidationError, match="bullet"):
        ExperienceEntry(title="Engineer", employer="Acme Ltd", bullet=["typo in key"])
