"""``render``: transformed content plus the unplaced Spans, filled into the
committed template. Observed only through the dumb ``all_text`` walker, as
the Phase 0 template smoke test is, since whatever the renderer becomes it
must still turn content into a document that passes these.
"""

import pytest
from docx_text import all_text
from render_support import to_transformed_content

from cvr.golden import CANDIDATES_DIR, load_candidate
from cvr.models import Span
from cvr.render import render
from cvr.template.build import BANNER, FOOTER, WORDMARK

PROFILE_HEADING = "Profile"


def _unplaced(*fragments: str) -> list[Span]:
    return [
        Span(block_id="body:0", start=0, end=len(text), text=text) for text in fragments
    ]


@pytest.fixture(scope="module")
def candidate():
    return load_candidate(CANDIDATES_DIR / "c01.json")


@pytest.fixture(scope="module")
def content(candidate):
    return to_transformed_content(candidate.content)


@pytest.fixture(scope="module")
def rendered(content) -> list[str]:
    return all_text(render(content, []))


def test_renders_the_name_and_a_bullet(candidate, rendered):
    assert candidate.content.name in rendered
    assert candidate.content.experience[0].bullets[0] in rendered


def test_no_tag_survives_rendering(rendered):
    assert not [text for text in rendered if "{{" in text or "{%" in text]


def test_the_wordmark_and_footer_are_present(rendered):
    assert WORDMARK in rendered
    assert FOOTER in rendered


def test_a_profile_renders_under_its_heading(candidate, rendered):
    assert PROFILE_HEADING in rendered
    assert candidate.content.profile[0] in rendered


def test_an_empty_profile_leaves_no_heading(content):
    without_profile = content.model_copy(update={"profile": []})
    assert PROFILE_HEADING not in all_text(render(without_profile, []))


def test_empty_certifications_and_additional_leave_no_stray_paragraphs(content):
    bare = content.model_copy(update={"certifications": [], "additional": []})
    text = all_text(render(bare, []))
    assert "Certifications" not in text
    assert "Additional Information" not in text


def test_the_banner_is_absent_when_nothing_is_unplaced(rendered):
    assert BANNER not in rendered


def test_the_banner_and_fragments_appear_when_text_is_unplaced(content):
    fragments = _unplaced("Available from 1 September", "Full clean driving licence")
    rendered = all_text(render(content, fragments))
    assert BANNER in rendered
    assert all(fragment.text in rendered for fragment in fragments)


def test_dates_and_the_employer_line_render_as_designed(candidate, rendered):
    first = candidate.content.experience[0]
    assert f"{first.start.expected} – {first.end.expected}" in rendered
    assert f"{first.employer}, {first.location}" in rendered
