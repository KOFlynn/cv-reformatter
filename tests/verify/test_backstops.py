"""The two backstops: regex over every block for emails, phones and URLs,
and the heading vocabulary over blocks holding no placed content. Both only
remove; neither places."""

import pytest
from support import block as _block
from support import labelling as _labelling
from support import ref as _ref

from cvr.models import RemovalLabel, RemovalRule
from cvr.verify import verify
from cvr.verify.backstops import HEADING_VOCABULARY, heading_key, pii_matches

# --- Regex backstop


def test_regex_backstop_catches_what_the_labelling_did_not_mention():
    blocks = [
        _block("body:0", "padraig.lonergan@example.net"),
        _block("body:1", "+353 83 555 0284"),
        _block("body:2", "https://www.linkedin.com/in/padraig-lonergan-fictional"),
    ]
    result = verify(blocks, _labelling())
    assert [(r.rule, r.subject.block_id, r.subject.text) for r in result.removals] == [
        (RemovalRule.EMAIL, "body:0", "padraig.lonergan@example.net"),
        (RemovalRule.PHONE, "body:1", "+353 83 555 0284"),
        (
            RemovalRule.URL,
            "body:2",
            "https://www.linkedin.com/in/padraig-lonergan-fictional",
        ),
    ]
    assert result.residue == []


def test_regex_backstop_matches_on_canonical_text_and_slices_raw():
    raw = "+353\u00a083\u00a0555\u00a00284"  # the text-box Layout's no-break spaces
    result = verify([_block("body:0", raw)], _labelling())
    assert result.removals[0].subject.text == raw


@pytest.mark.parametrize(
    "text",
    [
        "+353 83 555 0284",
        "085 555 0177",
        "+44 7700 900412",
        "+49 30 5550 1234",
        "+91 98765 43210",
        "(01) 555 0123",
        "085-555-0177",
    ],
)
def test_phone_pattern_accepts_the_golden_set_shapes(text):
    assert [(rule, start, end) for rule, start, end in pii_matches(text)] == [
        (RemovalRule.PHONE, 0, len(text))
    ]


@pytest.mark.parametrize(
    "text",
    [
        "2020-01 - 2021-06",
        "09/2017 - 09/2018",
        "2019-2022",
        "covering 400 users in total",
        "Y21 Z0Z0",
        "a 300-user department",
        "Jan 2020 - Present",
    ],
)
def test_phone_pattern_leaves_dates_and_counts_alone(text):
    assert pii_matches(text) == []


@pytest.mark.parametrize(
    ("text", "url"),
    [
        (
            "see https://github.com/jhellwig-fictional.",
            "https://github.com/jhellwig-fictional",
        ),
        (
            "www.costigan-design-fictional.example.com",
            "www.costigan-design-fictional.example.com",
        ),
        ("(https://example.org/a/b)", "https://example.org/a/b"),
    ],
)
def test_url_pattern_stops_before_trailing_punctuation(text, url):
    [(rule, start, end)] = pii_matches(text)
    assert rule is RemovalRule.URL and text[start:end] == url


def test_email_inside_an_llm_removal_is_reported_once():
    blocks = [_block("body:0", "Dr A Body, a.body@example.org")]
    result = verify(
        blocks,
        _labelling(
            removals=[
                RemovalLabel(
                    rule="RM_REFEREE",
                    block_id="body:0",
                    quote="Dr A Body, a.body@example.org",
                )
            ]
        ),
    )
    assert [r.rule for r in result.removals] == [RemovalRule.REFEREE]


# --- Heading backstop


def test_heading_backstop_removes_a_source_heading_from_an_unplaced_block():
    result = verify([_block("body:0", "Work History:")], _labelling())
    assert [(r.rule, r.subject.text) for r in result.removals] == [
        (RemovalRule.HEADING, "Work History:")
    ]
    assert result.residue == []


def test_heading_backstop_leaves_a_bold_job_title_alone():
    # A short unplaced line that is not in the vocabulary is unplaced text,
    # loud in the appendix, never silently removed.
    result = verify([_block("body:0", "Catchment Scientist")], _labelling())
    assert result.removals == []
    assert [span.text for span in result.unplaced] == ["Catchment Scientist"]


def test_heading_backstop_never_touches_a_block_with_placed_content():
    blocks = [_block("body:0", "Skills")]
    result = verify(blocks, _labelling(additional=[_ref("body:0", "Skills")]))
    assert result.removals == []
    assert result.content.additional[0].spans[0].text == "Skills"


def test_heading_backstop_is_whole_block_only():
    result = verify([_block("body:0", "Skills in demand")], _labelling())
    assert result.removals == []


@pytest.mark.parametrize(
    "text",
    [
        "Curriculum Vitae",
        "CURRICULUM VITAE",
        "Profile",
        "Key Skills",
        "Education",
        "Experience",
        "Certifications",
        "Additional Information",
        "References",
        "Contact",
        "Academic Background",
        "Referees",
        "Summary",
        "Skills",
        "Work History",
        "Other Information",
        "About Me",
        "Core Competencies",
        "Professional Experience",
        "Education & Training",
        "Education and Training",
        "Personal Statement",
        "Technical Skills",
        "Employment",
        "Further Information",
        "Qualifications",
        "Employment History :",
    ],
)
def test_heading_vocabulary_covers_the_four_layouts_and_common_synonyms(text):
    assert heading_key(text) in HEADING_VOCABULARY


@pytest.mark.parametrize(
    "text", ["Languages", "Interests", "Training", "Senior Engineer", "Padraig"]
)
def test_heading_vocabulary_is_narrow(text):
    # Sub-headings inside Additional Information are content, and a false
    # removal is silent.
    assert heading_key(text) not in HEADING_VOCABULARY
