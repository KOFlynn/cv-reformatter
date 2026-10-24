"""The path grammar's guard: a model-written path is recorded only if it is
made of known field names, brackets and digits."""

import pytest

from cvr.models import safe_path


@pytest.mark.parametrize(
    "path",
    [
        "name",
        "skills",
        "skills[3]",
        "removals[0]",
        "experience[0].title",
        "experience[2].bullets[11]",
        "education[1].details",
        "education[0].institution",
    ],
)
def test_a_path_of_the_grammar_is_kept(path):
    assert safe_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "Jo Bloggs",
        "name\n",
        "name ",
        "experience[0].Jo",
        "experience[x].title",
        "experience[-1].title",
        "experience[٣].title",  # a non-ASCII digit
        "skills[0",
        "a@b.example",
        "experience[" + "9" * 40 + "].title",
    ],
)
def test_anything_else_is_unknown(path):
    assert safe_path(path) == "unknown"
