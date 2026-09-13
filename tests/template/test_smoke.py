"""Smoke test: the template renders a Candidate's content through docxtpl.

Written against the ``fill`` seam and observed only through the dumb
``all_text`` walker so that Phase 1's render tests can reuse it unchanged:
whatever the renderer becomes, it must still turn content plus ``unplaced``
into a document that passes these.
"""

import pytest
from docx_text import all_text

from cvr.golden import CANDIDATES_DIR, load_candidate
from cvr.template import fill
from cvr.template.build import BANNER, FOOTER, WORDMARK

PROFILE_HEADING = "Profile"


@pytest.fixture(scope="module")
def content():
    return load_candidate(CANDIDATES_DIR / "c01.json").content


@pytest.fixture(scope="module")
def rendered(content) -> list[str]:
    return all_text(fill(content, unplaced=[]))


def test_renders_the_name_and_a_bullet(content, rendered):
    assert content.name in rendered
    assert content.experience[0].bullets[0] in rendered


def test_no_tag_survives_rendering(rendered):
    assert not [text for text in rendered if "{{" in text or "{%" in text]


def test_the_wordmark_and_footer_are_present(rendered):
    assert WORDMARK in rendered
    assert FOOTER in rendered


def test_a_profile_renders_under_its_heading(content, rendered):
    assert PROFILE_HEADING in rendered
    assert content.profile[0] in rendered


def test_an_empty_profile_leaves_no_heading(content):
    without_profile = content.model_copy(update={"profile": []})
    assert PROFILE_HEADING not in all_text(fill(without_profile, unplaced=[]))


def test_the_banner_is_absent_when_nothing_is_unplaced(rendered):
    assert BANNER not in rendered


def test_the_banner_and_fragments_appear_when_text_is_unplaced(content):
    fragments = ["Available from 1 September", "Full clean driving licence"]
    rendered = all_text(fill(content, unplaced=fragments))
    assert BANNER in rendered
    assert all(fragment in rendered for fragment in fragments)


def test_dates_and_the_employer_line_render_as_designed(content, rendered):
    first = content.experience[0]
    assert f"{first.start.expected} – {first.end.expected}" in rendered
    assert f"{first.employer}, {first.location}" in rendered
