"""``transform_content``: multi-span joins, date splitting wired into the
content tree, entry order applied, ``date_map``/``split_map`` assembled."""

from transform_support import multi_unit, unit

from cvr.models import (
    Span,
    VerifiedContent,
    VerifiedEducation,
    VerifiedExperience,
)
from cvr.transform import transform_content


def test_multi_span_unit_joins_with_one_space_and_logs_split_map() -> None:
    # "Called the office" <removed phone> "back the same day." clipped around
    # a mid-range removal, same block, ascending and non-overlapping.
    first = Span(block_id="body:3", start=0, end=18, text="Called the office ")
    second = Span(block_id="body:3", start=30, end=48, text="back the same day.")
    content = VerifiedContent(
        experience=[
            VerifiedExperience(bullets=[multi_unit(first, second)]),
        ]
    )
    result = transform_content(content)
    bullet = result.content.experience[0].bullets[0]
    assert bullet == "Called the office  back the same day."
    assert result.split_map[bullet] == [first, second]


def test_single_span_unit_never_enters_split_map() -> None:
    content = VerifiedContent(name=unit("Jane Doe"))
    result = transform_content(content)
    assert result.content.name == "Jane Doe"
    assert result.split_map == {}


def test_certification_date_like_text_is_never_touched() -> None:
    """Certifications are plain content; only an entry's ``dates`` reference
    goes through date parsing. A date-shaped string elsewhere in the tree
    must render verbatim, untouched."""
    content = VerifiedContent(certifications=[unit("Renewed March 2024")])
    result = transform_content(content)
    assert result.content.certifications == ["Renewed March 2024"]
    assert result.date_map == []


def test_entry_dates_split_into_start_and_end() -> None:
    content = VerifiedContent(
        experience=[
            VerifiedExperience(
                title=unit("Engineer"),
                dates=unit("Jan 2020 - Present", start=0),
            )
        ]
    )
    result = transform_content(content)
    entry = result.content.experience[0]
    assert entry.start == "01/2020"
    assert entry.end == "Present"
    assert [(date, span.text) for date, span in result.date_map] == [
        ("01/2020", "Jan 2020"),
        ("Present", "Present"),
    ]


def test_entry_order_is_applied_across_the_content_tree() -> None:
    content = VerifiedContent(
        experience=[
            VerifiedExperience(title=unit("Older"), dates=unit("2018 - 2019", start=0)),
            VerifiedExperience(
                title=unit("Newer"), dates=unit("2020 - Present", start=20)
            ),
        ]
    )
    result = transform_content(content)
    assert [entry.title for entry in result.content.experience] == ["Newer", "Older"]


def test_two_entries_sharing_a_date_log_a_pair_each() -> None:
    content = VerifiedContent(
        experience=[
            VerifiedExperience(title=unit("First"), dates=unit("2016", start=0)),
            VerifiedExperience(
                title=unit("Second"), dates=unit("2016", block_id="body:1")
            ),
        ]
    )
    result = transform_content(content)
    assert [(date, span.block_id) for date, span in result.date_map] == [
        ("2016", "body:0"),
        ("2016", "body:1"),
    ]


def test_education_entries_are_ordered_too() -> None:
    content = VerifiedContent(
        education=[
            VerifiedEducation(
                institution=unit("Older Uni"), dates=unit("2011", start=0)
            ),
            VerifiedEducation(
                institution=unit("Newer Uni"), dates=unit("2020", start=10)
            ),
        ]
    )
    result = transform_content(content)
    assert [entry.institution for entry in result.content.education] == [
        "Newer Uni",
        "Older Uni",
    ]


def test_multi_span_dates_are_not_split_but_are_logged() -> None:
    """A removal clipping the middle of a range block is not something any
    Candidate in the golden set produces, but the function must not crash:
    the whole thing is treated as one undated-for-ordering literal and
    recorded in ``split_map``, never ``date_map`` (no single raw slice)."""
    first = Span(block_id="body:5", start=0, end=8, text="Jan 2020")
    second = Span(block_id="body:5", start=20, end=27, text="Present")
    content = VerifiedContent(
        experience=[VerifiedExperience(dates=multi_unit(first, second))]
    )
    result = transform_content(content)
    entry = result.content.experience[0]
    assert entry.start is None
    assert entry.end == "Jan 2020 Present"
    assert result.date_map == []
    assert result.split_map == {"Jan 2020 Present": [first, second]}
